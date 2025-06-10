from dotenv import load_dotenv
load_dotenv(override=True)
from writing.service import writer_graph
from writing.writer_nodes import optimize_article

import json
import os
import re

from utils.wordpress import (
    get_jwt_token,
    post_article_to_wordpress,
    render_report_to_markdown,
    markdown_to_html,
)


def run_from_merge_input(path: str = "tests/test_merge_input.json"):
    # Load the previously saved writer input state (after interviews)
    with open(path, "r", encoding="utf-8") as f:
        merge_state = json.load(f)

    print("[DEBUG] ✅ Loaded merge state from file.")
    print("[DEBUG] Title:", merge_state.get("title"))
    print("[DEBUG] Sections:", len(merge_state.get("sections", [])), "total")

    # Run the writer graph
    result = writer_graph.invoke(merge_state)
    article = result.get("article")
    optimized_article = optimize_article(article)

    if not optimized_article:
        print("[ERROR] ❌ Writer returned no article.")
        return None

    # Step 1: Get WP token
    USERNAME = os.getenv("USERNAME_WP")
    PASSWORD = os.getenv("PASSWORD_WP")
    print(f"[DEBUG] USERNAME_WP={USERNAME}")

    token = get_jwt_token(USERNAME, PASSWORD)

    if not token:
        print("[ERROR] ❌ Failed to retrieve WordPress token.")
        return None

    # Step 2: Handle raw string article (likely JSON string)
    if isinstance(optimized_article, str):
        print(f"[DEBUG] Raw article string preview:\n{optimized_article[:200]}...")
        clean_article = re.sub(r"^```json|```$", "", optimized_article.strip(), flags=re.MULTILINE).strip()
        clean_article = clean_article.replace("–", ",")  # replace en dash

        try:
            parsed_article = json.loads(clean_article)
        except json.JSONDecodeError as e:
            print(f"[ERROR] Failed to parse article JSON: {e}")
            return None

        markdown = render_report_to_markdown(parsed_article)
        html = markdown_to_html(markdown)
        post_id = post_article_to_wordpress(parsed_article, token, html=html)
        return post_id

    # Step 3: Handle already-dict-formatted article
    try:
        markdown = render_report_to_markdown(article)
        html = markdown_to_html(markdown)
        post_id = post_article_to_wordpress(article, token, html=html)
        return post_id
    except Exception as e:
        print(f"[ERROR] Unexpected failure during render/publish: {e}")
        return None


if __name__ == "__main__":
    post_id = run_from_merge_input()
    if post_id:
        print(f"[✅] Article published. Post ID: {post_id}")
    else:
        print("[❌] Article publication failed.")

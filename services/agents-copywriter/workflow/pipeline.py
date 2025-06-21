from team.journalists_service import journalist_team_graph
from interview.interview_service import run_interviews_parallel_threaded  # Use threaded version
from writing.service import writer_graph
from writing.writer_nodes import optimize_article
from interview.interview import InterviewSession
from langchain_core.messages import HumanMessage
from utils.wordpress import get_jwt_token, post_article_to_wordpress
from utils.wordpress import render_report_to_markdown, markdown_to_html
from utils.prompts import load_prompt_template
from utils.headline_distribution import distribute_headlines_to_journalists
from uuid import uuid4
import os
import json
import re
from metadata_model import MetadataInput, CopywriterRequest


def run_full_article_pipeline(request: CopywriterRequest):  # Remove async
    """
    Updated pipeline to work with metadata input from metadata-generator (SYNC VERSION)
    """
    metadata = request.metadata
    thread_id = f"article-{metadata.main_kw.replace(' ', '-').lower()}"
    thread = {"configurable": {"thread_id": thread_id}}

    # Step 1: Journalist team creation using metadata
    setup = journalist_team_graph.invoke({
        "topic": metadata.main_kw,
        "title": f"Les meilleures {metadata.main_kw} en 2025",  # Generate title from main keyword
        "type": metadata.post_type,
        "keywords": [metadata.main_kw] + metadata.secondary_kws,
        "team_title": metadata.headlines[:3],  # Use first 3 headlines as team roles
        "audience": request.audience,
        "prompt": f"Write about {metadata.main_kw} following these headlines: {', '.join(metadata.headlines)}",
        "number_of_journalists": request.number_of_journalists,
        "editor_feedback": "",
        "journalists": [],
        "headlines": metadata.headlines  # Add headlines to setup
    }, thread)

    journalists_without_headlines = setup["journalists"]

    # Step 1.5: Distribute headlines among journalists
    final_journalists = distribute_headlines_to_journalists(
        journalists_without_headlines,
        metadata.headlines
    )

    report_structure = load_prompt_template(metadata.post_type)

    # Step 2: Run interviews in parallel using threading (FIXED!)
    print(f"[DEBUG] Starting {len(final_journalists)} interviews using THREADING...")
    all_sections = run_interviews_parallel_threaded(  # Use sync threaded version
        journalists=final_journalists,
        topic=metadata.main_kw,
        audience=request.audience,
        report_structure=report_structure,
        max_turns=request.max_turns
    )
    print(f"[DEBUG] ✅ Threaded interviews completed! Got {len(all_sections)} sections")

    # Step 3: Merge all interviews into one article
    merge_state = {
        "title": f"Les meilleures {metadata.main_kw} en 2025",
        "sections": all_sections,
        "audience": request.audience,
        "report_structure": report_structure,
        "headlines": metadata.headlines,  # Pass headlines from metadata
        "post_type": metadata.post_type  # Pass post_type from metadata
    }

    # 💾 Save intermediate state for debugging or replay
    with open("test_merge_input.json", "w", encoding="utf-8") as f:
        json.dump(merge_state, f, indent=2, ensure_ascii=False)
        print("[DEBUG] Saved merge state to test_merge_input.json")

    # Step 4: Generate article using writer graph
    final_output = writer_graph.invoke(merge_state)
    article = final_output.get("article")
    print("Merging datas..")
    if not article:
        print(f"[ERROR] ❌ 'article' missing from writer output: {final_output}")
        return None

    # Step 5: Optimize article
    print("Starting optimization..")
    optimized_article = optimize_article(article, metadata.headlines)  # Pass headlines
    if not optimized_article:
        print("[ERROR] ❌ Optimizer returned nothing.")
        return None

    # Step 6: Authenticate with WordPress
    USERNAME = os.getenv("USERNAME_WP")
    PASSWORD = os.getenv("PASSWORD_WP")
    print(f"[DEBUG] USERNAME_WP={USERNAME}")
    token = get_jwt_token(USERNAME, PASSWORD)

    if not token:
        print("[ERROR] ❌ Failed to retrieve WordPress token.")
        return None

    # Step 7: Parse and format final article
    if isinstance(optimized_article, str):
        print("[DEBUG] optimized_article is a string, attempting to parse JSON.")
        print(f"[DEBUG] Raw article string preview:\n{optimized_article[:200]}...")
        clean_article = re.sub(r"^```json|```$", "", optimized_article.strip(), flags=re.MULTILINE).strip()
        clean_article = clean_article.replace("–", ",")

        try:
            parsed_article = json.loads(clean_article)
            print("[DEBUG] ✅ Successfully parsed optimized article.")
        except json.JSONDecodeError as e:
            print(f"[ERROR] Failed to parse optimized article: {e}")
            return None
    else:
        print("[DEBUG] optimized_article is already a dict.")
        parsed_article = optimized_article

    # Step 8: Convert to markdown and publish
    try:
        # Add post_type to the parsed article for the renderer
        if isinstance(parsed_article, dict):
            parsed_article['post_type'] = metadata.post_type

        markdown = render_report_to_markdown(parsed_article)
        html = markdown_to_html(markdown)
        post_id = post_article_to_wordpress(parsed_article, token, html=html)
        return post_id
    except Exception as e:
        print(f"[ERROR] 💥 Unexpected failure during render or publish: {e}")
        return None
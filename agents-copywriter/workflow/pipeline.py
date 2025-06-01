from team.journalists_service import journalist_team_graph
from interview.interview_service import interview_graph
from writing.service import writer_graph
from writing.writer_nodes import optimize_article
from interview.interview import InterviewSession
from langchain_core.messages import HumanMessage
from utils.wordpress import get_jwt_token, post_article_to_wordpress
from utils.wordpress import render_report_to_markdown, markdown_to_html
from utils.prompts import load_prompt_template
from uuid import uuid4
import os
import json
import re


async def run_full_article_pipeline(row):
    thread_id = f"article-{row['Title'].replace(' ', '-').lower()}"
    thread = {"configurable": {"thread_id": thread_id}}

    # Step 1: Journalist team creation
    setup = journalist_team_graph.invoke({
        "topic": row["Topic"],
        "title": row["Title"],
        "type": row["Type"],
        "keywords": row["Keywords"],
        "team_title": row.get("TeamTitle", []),
        "audience": row["Audience"],
        "prompt": row["Prompt"],
        "number_of_journalists": 3,
        "editor_feedback": "",
        "journalists": []
    }, thread)

    final_journalists = setup["journalists"]
    report_structure = load_prompt_template(row["Type"])
    all_sections = []

    # Step 2: Interview each journalist
    for journalist in final_journalists:
        interview_state = InterviewSession(
            journalist=journalist,
            audience=row["Audience"],
            report_structure=report_structure,
            messages=[HumanMessage(content="Hello, I’m ready to begin our conversation.")],
            max_turns=3,
            sources=[],
            full_conversation="",
            report_sections=[]
        )
        interview_thread = {"configurable": {"thread_id": f"{thread_id}-interview-{uuid4()}"}}
        result = interview_graph.invoke(interview_state, interview_thread)
        all_sections.extend(result.get("report_sections", []))

    # Step 3: Merge all interviews into one article
    merge_state = {
        "title": row["Title"],
        "sections": all_sections,
        "audience": row["Audience"],
        "report_structure": report_structure
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
    optimized_article = optimize_article(article)
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
        markdown = render_report_to_markdown(parsed_article)
        html = markdown_to_html(markdown)
        post_id = post_article_to_wordpress(parsed_article, token, html=html)
        return post_id
    except Exception as e:
        print(f"[ERROR] 💥 Unexpected failure during render or publish: {e}")
        return None

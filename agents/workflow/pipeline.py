from team.journalists_service import journalist_team_graph
from interview.interview_service import interview_graph
from writing.service import writer_graph
from interview.interview import InterviewSession
from langchain_core.messages import HumanMessage
from utils.wordpress import get_jwt_token, post_article_to_wordpress
from utils.wordpress import render_report_to_markdown, markdown_to_html
from utils.prompts import load_prompt_template
from uuid import uuid4
import os
import json

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

    final_output = writer_graph.invoke(merge_state)

    # Step 4: Authenticate with WordPress
    USERNAME = os.getenv("USERNAME_WP")
    PASSWORD = os.getenv("PASSWORD_WP")
    token = get_jwt_token(USERNAME, PASSWORD)

    # Step 5: Parse and publish
    article = final_output.get("article")

    if not article:
        print(f"[ERROR] ❌ 'article' field is missing or empty in writer output: {final_output}")
        return None

    if isinstance(article, str):
        print(f"[DEBUG] Raw article string: {article[:200]}...")
        html = markdown_to_html(article)
        post_id = post_article_to_wordpress(
            {"title": row["Title"]},
            token,
            html=html
        )
        return post_id

    # Fallback in case article is not a string
    print("[ERROR] ⚠️ Unexpected article format:", type(article))
    return None

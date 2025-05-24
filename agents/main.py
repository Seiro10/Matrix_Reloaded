from dotenv import load_dotenv
import os
import csv
import json
import sys
import re
from uuid import uuid4
from langchain_core.messages import HumanMessage
import json5

from team.journalists_service import journalist_team_graph
from team.journalists_team import Journalist
from interview.interview_service import interview_graph
from interview.interview import InterviewSession
from utils.prompts import load_prompt_template
from utils.wordpress import get_jwt_token, post_article_to_wordpress


# 🌍 Load environment variables
load_dotenv()
USERNAME = os.getenv("USERNAME_WP")
PASSWORD = os.getenv("PASSWORD_WP")

# 🔐 Authenticate once for WordPress
jwt_token = get_jwt_token(USERNAME, PASSWORD)
if not jwt_token:
    raise SystemExit("[FATAL] ❌ Failed to get JWT token. Exiting.")

# 🚀 Process each article in the CSV
with open("articles.csv", newline='', encoding='utf-8') as csvfile:
    reader = csv.DictReader(csvfile)
    for row in reader:
        print(f"\n📝 Processing Article: {row['Title']}")

        # 📌 Build thread ID and input state
        thread_id = f"article-{row['Title'].replace(' ', '-').lower()}"
        thread = {"configurable": {"thread_id": thread_id}}

        # 🧠 STEP 1: Build the team of journalists
        setup = journalist_team_graph.invoke({
            "topic": row["Topic"],
            "title": row["Title"],
            "type": row["Type"],
            "keywords": row["Keywords"].split(","),
            "team_title": row.get("TeamTitle", "").split(",") if row.get("TeamTitle") else [],
            "audience": row["Audience"],
            "prompt": row["Prompt"],
            "number_of_journalists": 3,
            "editor_feedback": "",
            "journalists": []
        }, thread)

        for journalist in setup["journalists"]:
            print(journalist.profile)

        # ✍️ Optionally allow manual feedback
        feedback = input("\nEnter feedback for improving this team (or press Enter to skip): ").strip()
        if feedback:
            journalist_team_graph.update_state(thread, {"editor_feedback": feedback}, as_node="human_feedback")
            for event in journalist_team_graph.stream(None, thread, stream_mode="values"):
                for journalist in event.get("journalists", []):
                    print(journalist.profile)

        # ✅ Finalize the team
        journalist_team_graph.update_state(thread, {"editor_feedback": None}, as_node="human_feedback")
        journalist_team_graph.stream(None, thread, stream_mode="values")
        final_state = journalist_team_graph.get_state(thread)
        final_journalists = final_state.values["journalists"]

        # 💡 Load JSON report template
        report_structure = load_prompt_template(row["Type"])

        # 🎤 STEP 2: Interview each journalist
        for journalist in final_journalists:
            print(f"\n🎤 Starting interview with: {journalist.full_name}")

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
            print(f"[DEBUG] Executing interview graph for thread: {interview_thread['configurable']['thread_id']}")

            # ⛓ Run the interview graph to completion
            final_state = interview_graph.invoke(interview_state, interview_thread)

            # 📄 Display and publish report
            if "report_sections" in final_state:
                for section in final_state["report_sections"]:
                    print("\n🧾 REPORT SECTION (preview):\n")
                    print(str(section)[:500])  # preview
                    print(f"[DEBUG] Raw section content for {journalist.full_name}:\n{section}")
                    try:
                        if isinstance(section, dict):
                            json_report = section
                        else:
                            clean_section = re.sub(r"^```(?:json)?|```$", "", section.strip(),
                                                   flags=re.MULTILINE).strip()
                            try:
                                json_report = json.loads(clean_section)  # strict parse
                            except json.JSONDecodeError:
                                print(f"[WARN] Trying fallback JSON5 parser due to format error.")
                                json_report = json5.loads(clean_section)  # allows trailing commas etc.

                        post_id = post_article_to_wordpress(json_report, jwt_token)

                        if post_id:
                            print(f"[✅] Article '{json_report['title']}' published as private (Post ID: {post_id})")
                        else:
                            print(f"[❌] Failed to publish: {json_report['title']}")
                    except json.JSONDecodeError as jde:
                        print(f"[ERROR] 💥 JSON Decode Error for {journalist.full_name}: {jde}")
                    except NameError as ne:
                        print(f"[ERROR] 💥 NameError (possibly 'unicode') in response for {journalist.full_name}: {ne}")
                    except Exception as e:
                        print(f"[ERROR] 💥 Unexpected failure for {journalist.full_name}: {e}")


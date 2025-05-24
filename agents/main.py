import csv
from uuid import uuid4
from langchain_core.messages import HumanMessage

from team.journalists_service import journalist_team_graph
from team.journalists_team import Journalist
from interview.interview_service import interview_graph
from interview.interview import InterviewSession

# 🚀 Load and process each article from the CSV
with open("articles.csv", newline='', encoding='utf-8') as csvfile:
    reader = csv.DictReader(csvfile)
    for row in reader:
        print(f"\n📝 Processing Article: {row['Title']}")

        # 🧠 Step 1: Build team of journalists
        thread_id = f"article-{row['Title'].replace(' ', '-').lower()}"
        thread = {"configurable": {"thread_id": thread_id}}

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

        # ✏️ Optional: live feedback (comment out for batch runs)
        feedback = input("\nEnter feedback for improving this team (or press Enter to skip): ").strip()
        if feedback:
            journalist_team_graph.update_state(thread, {"editor_feedback": feedback}, as_node="human_feedback")
            for event in journalist_team_graph.stream(None, thread, stream_mode="values"):
                for journalist in event.get("journalists", []):
                    print(journalist.profile)

        # ✅ Clear feedback and finalize state
        journalist_team_graph.update_state(thread, {"editor_feedback": None}, as_node="human_feedback")
        journalist_team_graph.stream(None, thread, stream_mode="values")
        final_state = journalist_team_graph.get_state(thread)
        final_journalists = final_state.values["journalists"]

        # 🎤 Step 2: Run interviews for each journalist
        for journalist in final_journalists:
            print(f"\n🎤 Starting interview with: {journalist.full_name}")

            interview_state = InterviewSession(
                journalist=journalist,
                messages=[HumanMessage(content="Hello, I’m ready to begin our conversation.")],
                max_turns=3,
                sources=[],
                full_conversation="",
                report_sections=[]
            )

            interview_thread = {"configurable": {"thread_id": f"{thread_id}-interview-{uuid4()}"}}

            for event in interview_graph.stream(interview_state, interview_thread):
                if "full_conversation" in event:
                    print("\n📄 INTERVIEW TRANSCRIPT:\n")
                    print(event["full_conversation"])

                if "report_sections" in event:
                    print("\n🧾 REPORT SECTION:\n")
                    for section in event["report_sections"]:
                        print(section)

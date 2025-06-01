import csv
from agents.team.journalists_service import journalist_team_graph

with open("articles.csv", newline='', encoding='utf-8') as csvfile:
    reader = csv.DictReader(csvfile)
    for row in reader:
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
        }, {"configurable": {"thread_id": f"article-{row['Title'].replace(' ', '-').lower()}"}})

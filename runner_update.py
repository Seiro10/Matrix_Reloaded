from dotenv import load_dotenv
load_dotenv()
from agents.update.service import build_graph_update
from core.state import GraphState
import json

dummy_state = {
    "subject": "Top 10 champions late game LoL",
    "type": "test",
    "keywords": ["lategame", "champions", "lol"],
    "article_url": "https://...",
    "transcript_url": "https://...",
    "last_modified": "2024-05-20",
    "article_html": open("logs/cleaned_article.html").read(),
    "transcript_text": open("logs/transcripts/7jGGE_9vFQ4.txt").read()[:3000],
    "reconstructed_html": open("logs/reconstructed.html").read(),
    "diagnosis": None,
    "generated_sections": None,
    "merged_html": None,
    "final_html": None
}

if __name__ == "__main__":
    update = build_graph_update()
    updated_state = update.invoke(dummy_state)

    with open("logs/reconstructed.html", "w", encoding="utf-8") as f:
        f.write(updated_state["reconstructed_html"])

    with open("logs/diagnosis.json", "w", encoding="utf-8") as f:
        json.dump(updated_state["diagnosis"], f, ensure_ascii=False, indent=2)

    print("\n✅ HTML reconstruit (300 premiers caractères) :\n")
    print(updated_state["reconstructed_html"][:300])


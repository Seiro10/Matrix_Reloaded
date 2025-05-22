from dotenv import load_dotenv
load_dotenv()

from agents.writing.service import writing_node_service
from core.state import GraphState
import json

if __name__ == "__main__":
    with open("logs/diagnosis.json", "r", encoding="utf-8") as f:
        diagnosis = json.load(f)

    dummy_state = {
        "subject": "Top 10 champions late game LoL",
        "type": "test",
        "keywords": ["lategame", "champions", "lol"],
        "article_url": "https://...",
        "transcript_url": "https://...",
        "last_modified": "2024-05-20",
        "article_html": open("logs/cleaned_article.html").read(),
        "transcript_text": open("logs/transcripts/7jGGE_9vFQ4.txt").read(),
        "reconstructed_html": open("logs/reconstructed.html").read(),
        "diagnosis": diagnosis,
        "generated_sections": None,
        "merged_html": None,
        "final_html": None
    }

    writer = writing_node_service()
    result_state = writer.invoke(dummy_state)

    with open("logs/generated_sections.json", "w", encoding="utf-8") as f:
        json.dump(result_state["generated_sections"], f, ensure_ascii=False, indent=2)

    print("\n✅ Sections générées (extrait) :\n")
    for section in result_state["generated_sections"][:2]:
        print(f"→ {section['title'][:60]}...\n{section['updated_html'][:300]}\n")

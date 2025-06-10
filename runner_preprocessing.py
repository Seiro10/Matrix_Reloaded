import os
import re
from dotenv import load_dotenv
load_dotenv()
from agents.preprocessing.service import preprocessing_node
from langgraph.checkpoint.memory import InMemorySaver

OUTPUT_DIR = "logs/transcripts"
os.makedirs("logs", exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

def extract_video_id(url: str) -> str:
    match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11})(?:&|$)", url)
    return match.group(1) if match else "unknown_video"

dummy_state = {
    "subject": "Top 10 des champions en lategame sur league of legends",
    "article_url": "https://stuffgaming.fr/meilleurs-champions-lategame/",
    "transcript_url": "https://www.youtube.com/watch?v=7jGGE_9vFQ4&ab_channel=SkillCappedChallengerLoLGuides",
    "article_html": None,
    "transcript_text": None,
    "reconstructed_html": None,
    "diagnosis": None,
    "generated_sections": None,
    "merged_html": None,
    "final_html": None,
    "keywords": ["lategame lol", "meilleurs champions", "scaling"],
    "type": "test",
    "last_modified": None
}

if __name__ == "__main__":
    print("[PREPROCESS] 🚀 Lancement du test du service preprocessing...\n")

    checkpointer = InMemorySaver()
    graph = preprocessing_node().with_config(checkpointer=checkpointer)

    updated_state = graph.invoke(dummy_state, config={
        "configurable": {
            "thread_id": "demo-thread-001",
            "user_id": "agent_preprocessing"
        }
    })

    print("\n✅ ARTICLE HTML (nettoyé, 1500 premiers caractères) :\n")
    print(updated_state["article_html"][:1500])

    print("\n✅ TRANSCRIPT (nettoyé, 300 premiers caractères) :\n")
    print(updated_state["transcript_text"][:300])

    with open("logs/cleaned_article.html", "w", encoding="utf-8") as f:
        f.write(updated_state["article_html"])

    video_id = extract_video_id(dummy_state["transcript_url"])
    with open(f"{OUTPUT_DIR}/{video_id}.txt", "w", encoding="utf-8") as f:
        f.write(updated_state["transcript_text"])

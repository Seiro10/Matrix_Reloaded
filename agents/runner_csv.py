import csv
import requests
from agents.orchestrator import run_orchestration

def load_html_from_url(url):
    res = requests.get(url)
    return res.text if res.status_code == 200 else ""

def run_batch(csv_path: str):
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            subject = row["subject"]
            article_html = load_html_from_url(row["article_url"])
            transcript_txt = load_html_from_url(row["transcript_url"])  # Ou parsing spécifique
            keywords = [kw for kw in [row["kw1"], row.get("kw2", ""), row.get("kw3", "")] if kw.strip()]

            result = run_orchestration(subject, article_html, transcript_txt, keywords)
            print(f"\n🧠 Sujet : {subject}\n➡️ Sections suggérées :\n{result}\n")

# Exemple d'utilisation
if __name__ == "__main__":
    run_batch("inputs/articles.csv")

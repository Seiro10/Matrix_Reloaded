from dotenv import load_dotenv
import os

# ✅ Load .env from current directory
env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path=env_path, override=True)

# 🧪 Debug: show the loaded value
print("[DEBUG] USERNAME_WP =", os.getenv("USERNAME_WP"))

import os
import json
import requests
import markdown
from slugify import slugify  # pip install python-slugify
import ast

# -----------------------------
# 1. Convert structured JSON to Markdown
# -----------------------------
def render_report_to_markdown(data: dict) -> str:
    md = f"# {data['title']}\n\n"

    # ✏️ Introduction sans titre de section
    intro = data.get('introduction', {})
    if intro.get('teaser'):
        md += f"{intro['teaser']}\n\n"
    for bullet in intro.get('bullets', []):
        md += f"- {bullet}\n"
    if intro.get('hook2'):
        for hook2 in intro['hook2']:
            md += f"\n{hook2}\n"
    md += "\n"

    # 🖱️ Comparisons
    for item in data.get('comparisons', []):
        md += f"### {item['title']}: {item['product']}\n\n"
        md += f"{item['description']}\n\n"
        for i in range(1, 5):
            para = item.get(f"paragraph{i}")
            if para:
                md += f"{para}\n\n"
        if item.get("pros"):
            md += "**Pros:**\n" + "".join(f"- ✅ {p}\n" for p in item["pros"]) + "\n"
        if item.get("cons"):
            md += "**Cons:**\n" + "".join(f"- ❌ {c}\n" for c in item["cons"]) + "\n"
        md += "\n"

    # 📌 Notable Mentions
    if data.get("notable_mentions"):
        md += "## Notable Mentions\n"
        for mention in data["notable_mentions"]:
            md += f"**{mention['title']}**: {mention['description']}\n\n"

    # 🔄 Updates
    if data.get("updates"):
        md += "## Updates\n"
        for update in data["updates"]:
            md += f"- {update}\n"
        md += "\n"

    # ✅ Conclusion
    if data.get("conclusion"):
        md += "## Conclusion\n"
        md += f"{data['conclusion']['summary']}\n\n"
        for rec in data['conclusion'].get("recommendations", []):
            md += f"- {rec}\n"
        md += "\n"

    # ❓ FAQ
    if data.get("faq"):
        md += "## FAQ\n"
        if data.get("faq_description"):
            md += f"{data['faq_description']}\n\n"
        for q in data["faq"]:
            md += f"**Q: {q['question']}**\n\nA: {q['answer']}\n\n"

    return md.strip()


# -----------------------------
# 2. Markdown → HTML
# -----------------------------
def markdown_to_html(markdown_content: str) -> str:
    return markdown.markdown(markdown_content)


# -----------------------------
# 3. Create Article on WordPress (POST)
# -----------------------------
def post_article_to_wordpress(article_json: dict, jwt_token: str, html: str = None) -> str:
    post_url = "https://stuffgaming.fr/wp-json/wp/v2/posts"
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Content-Type": "application/json"
    }

    payload = {
        "title": article_json["title"],
        "slug": slugify(article_json["title"]),
        "content": html or "",  # fallback
        "status": "private"
    }

    try:
        print(f"[DEBUG] ➕ Envoi de la création d'article vers {post_url}")
        res = requests.post(post_url, headers=headers, json=payload)
        res.raise_for_status()
        article_id = res.json().get("id")
        print(f"[✅] Article créé avec succès: ID = {article_id}")
        return article_id
    except Exception as e:
        print(f"[ERROR] ❌ Échec de création de l’article : {e}")
        if res is not None:
            print(f"[DEBUG] ↪ Status: {res.status_code}")
            print(f"[DEBUG] ↪ Response: {res.text}")
        return None

# -----------------------------
# 4. Token Acquisition (already works)
# -----------------------------
def get_jwt_token(username, password):
    auth_url = "https://stuffgaming.fr/wp-json/jwt-auth/v1/token"
    payload = {
        "username": username,
        "password": password
    }

    try:
        print(f"[DEBUG] Requête POST vers {auth_url} avec user={username}")
        res = requests.post(auth_url, json=payload)
        res.raise_for_status()
        token = res.json().get("token")
        print("[DEBUG] ✅ Token JWT récupéré avec succès.")
        return token
    except Exception as e:
        print(f"[ERROR] ❌ Échec de récupération du token JWT : {e}")
        if res is not None:
            print(f"[DEBUG] ↪ Statut HTTP : {res.status_code}")
            print(f"[DEBUG] ↪ Réponse brute : {res.text}")
        return None

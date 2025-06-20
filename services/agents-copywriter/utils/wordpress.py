from dotenv import load_dotenv
import os

# ✅ Load .env from current directory
env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path=env_path, override=True)

import json
import requests
import markdown
from slugify import slugify  # pip install python-slugify
import ast


# -----------------------------
# 1. Auto-detect structure type and convert to Markdown
# -----------------------------
def detect_structure_type(data: dict) -> str:
    """
    Detect the type of JSON structure based on available keys
    """
    if 'headings_content' in data:
        return 'headings_content'
    elif 'comparisons' in data:
        return 'comparisons'
    elif 'sections' in data:
        return 'sections'
    else:
        return 'unknown'


def render_headings_content_structure(data: dict) -> str:
    """
    Render the headings_content structure (new format)
    """
    md = ""
    headings_content = data.get('headings_content', {})

    for key, content in headings_content.items():
        if key == 'description':
            continue  # Skip meta description

        if isinstance(content, dict) and content.get('heading') and content.get('paragraph'):
            md += f"## {content['heading']}\n\n"
            md += f"{content['paragraph']}\n\n"

    return md


def render_comparisons_structure(data: dict) -> str:
    """
    Render the comparisons structure (affiliate format)
    """
    md = ""

    # 🖱️ Comparisons
    for item in data.get('comparisons', []):
        md += f"## {item['title']}: {item.get('product', '')}\n\n"

        if item.get('description'):
            md += f"{item['description']}\n\n"

        # Handle paragraphs
        for i in range(1, 5):
            para = item.get(f"paragraph{i}")
            if para:
                md += f"{para}\n\n"

        # Handle pros/cons
        if item.get("pros"):
            md += "**Avantages:**\n" + "".join(f"- ✅ {p}\n" for p in item["pros"]) + "\n"
        if item.get("cons"):
            md += "**Inconvénients:**\n" + "".join(f"- ❌ {c}\n" for c in item["cons"]) + "\n"
        md += "\n"

    # 📌 Notable Mentions
    if data.get("notable_mentions"):
        md += "## Mentions Spéciales\n\n"
        for mention in data["notable_mentions"]:
            md += f"### {mention['title']}\n\n"
            md += f"{mention['description']}\n\n"

    return md


def render_sections_structure(data: dict) -> str:
    """
    Render the sections structure (generic format)
    """
    md = ""

    for section in data.get('sections', []):
        if isinstance(section, dict):
            if section.get('title'):
                md += f"## {section['title']}\n\n"
            if section.get('content'):
                md += f"{section['content']}\n\n"
        elif isinstance(section, str):
            md += f"{section}\n\n"

    return md


def render_introduction(data: dict) -> str:
    """
    Render introduction section (works for all formats)
    """
    md = ""
    intro = data.get('introduction', {})

    if intro.get('teaser'):
        md += f"{intro['teaser']}\n\n"

    # Handle different intro formats
    if intro.get('nlp_answer'):
        md += f"{intro['nlp_answer']}\n\n"

    if intro.get('extended_answer'):
        md += f"{intro['extended_answer']}\n\n"

    if intro.get('bullets'):
        for bullet in intro['bullets']:
            md += f"- {bullet}\n"
        md += "\n"

    if intro.get('hook2'):
        if isinstance(intro['hook2'], list):
            for hook in intro['hook2']:
                md += f"{hook}\n\n"
        else:
            md += f"{intro['hook2']}\n\n"

    return md


def render_conclusion(data: dict) -> str:
    """
    Render conclusion section (works for all formats)
    """
    md = ""

    if data.get("conclusion"):
        md += "## Conclusion\n\n"
        conclusion = data['conclusion']

        if conclusion.get('summary'):
            md += f"{conclusion['summary']}\n\n"

        if conclusion.get('closing_sentence'):
            md += f"{conclusion['closing_sentence']}\n\n"

        # Handle recommendations (old format)
        if conclusion.get('recommendations'):
            md += "**Nos recommandations:**\n\n"
            for rec in conclusion['recommendations']:
                md += f"- {rec}\n"
            md += "\n"

    return md


def render_faq(data: dict) -> str:
    """
    Render FAQ section (works for all formats)
    """
    md = ""

    if data.get("faq"):
        md += "## Questions Fréquentes\n\n"

        if data.get("faq_description"):
            md += f"{data['faq_description']}\n\n"

        for q in data["faq"]:
            md += f"### {q['question']}\n\n"
            md += f"{q['answer']}\n\n"

    return md


def render_report_to_markdown(data: dict) -> str:
    """
    Adaptive markdown renderer that detects structure type automatically
    """
    # Start with title
    md = f"# {data.get('title', 'Article')}\n\n"

    # Detect structure type
    structure_type = detect_structure_type(data)
    print(f"[DEBUG] Detected structure type: {structure_type}")

    # Render introduction (common to all)
    md += render_introduction(data)

    # Render main content based on structure type
    if structure_type == 'headings_content':
        print("[DEBUG] Using headings_content renderer")
        md += render_headings_content_structure(data)

    elif structure_type == 'comparisons':
        print("[DEBUG] Using comparisons renderer")
        md += render_comparisons_structure(data)

    elif structure_type == 'sections':
        print("[DEBUG] Using sections renderer")
        md += render_sections_structure(data)

    else:
        print(f"[WARNING] Unknown structure type: {structure_type}, using fallback")
        # Fallback: try to render any content we can find
        if 'content' in data:
            md += f"{data['content']}\n\n"

    # Handle updates (if present)
    if data.get("updates"):
        md += "## Mises à jour\n\n"
        for update in data["updates"]:
            md += f"- {update}\n"
        md += "\n"

    # Render conclusion (common to all)
    md += render_conclusion(data)

    # Render FAQ (common to all)
    md += render_faq(data)

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

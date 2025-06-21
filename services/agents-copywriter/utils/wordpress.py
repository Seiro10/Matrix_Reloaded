from dotenv import load_dotenv
import os
import re

env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path=env_path, override=True)

import json
import requests
import markdown
from slugify import slugify
import ast


def format_text_with_structure(text: str) -> str:
    """
    Convert structured text patterns to proper markdown formatting
    """
    if not text:
        return text

    # Don't process text that's already well-formatted or doesn't need formatting
    if len(text) < 50:  # Short text probably doesn't need complex formatting
        return text

    # Convert numbered lists: "1) Item" or "1. Item" to markdown
    text = re.sub(r'(\d+)\)\s*([^\n]+)', r'1. \2', text)

    # Convert bullet points: "• Item" to markdown (preserve existing markdown)
    text = re.sub(r'•\s*([^\n]+)', r'- \1', text)

    # Convert checkmarks to emojis but preserve existing structure
    text = re.sub(r'✓\s*([^\n]+)', r'- ✅ \1', text)
    text = re.sub(r'✗\s*([^\n]+)', r'- ❌ \1', text)

    return text


def render_affiliate_article(data: dict) -> str:
    """
    Renderer for Affiliate articles (comparisons structure)
    """
    md = ""

    # 1. Title
    if data.get('title'):
        md += f"# {data['title']}\n\n"

    # 2. Introduction
    intro = data.get('introduction', {})
    if intro.get('paragraphs'):
        for paragraph in intro['paragraphs']:
            md += f"{paragraph}\n\n"

    if intro.get('bullets'):
        for bullet in intro['bullets']:
            md += f"{bullet}\n\n"

    # 3. Comparisons (main content for affiliate)
    for comparison in data.get('comparisons', []):
        # Product title
        product_title = comparison.get('title', '')
        product_name = comparison.get('product', '')
        if product_name:
            md += f"## {product_title}: {product_name}\n\n"
        else:
            md += f"## {product_title}\n\n"

        # Description
        if comparison.get('description'):
            md += f"{comparison['description']}\n\n"

        # Paragraphs (paragraph1, paragraph2, etc.)
        for i in range(1, 5):
            para = comparison.get(f'paragraph{i}')
            if para:
                md += f"{para}\n\n"

        # Pros and Cons
        if comparison.get('pros'):
            md += "**Avantages :**\n"
            for pro in comparison['pros']:
                md += f"- ✅ {pro}\n"
            md += "\n"

        if comparison.get('cons'):
            md += "**Inconvénients :**\n"
            for con in comparison['cons']:
                md += f"- ❌ {con}\n"
            md += "\n"

    # 4. Notable Mentions
    if data.get('notable_mentions'):
        md += "## Mentions Spéciales\n\n"
        for mention in data['notable_mentions']:
            md += f"### {mention['title']}\n\n"
            md += f"{mention['description']}\n\n"

    # 5. Updates
    if data.get('updates'):
        md += "## Mises à jour\n\n"
        for update in data['updates']:
            md += f"- {update}\n"
        md += "\n"

    # 6. Conclusion
    conclusion = data.get('conclusion', {})
    if conclusion:
        md += "## Conclusion\n\n"

        if conclusion.get('summary'):
            md += f"{conclusion['summary']}\n\n"

        if conclusion.get('recommendations'):
            md += "**Nos recommandations :**\n"
            for rec in conclusion['recommendations']:
                md += f"- {rec}\n"
            md += "\n"

    # 7. FAQ
    if data.get('faq'):
        md += "## Questions Fréquentes\n\n"

        if data.get('faq_description'):
            md += f"{data['faq_description']}\n\n"

        for faq_item in data['faq']:
            if faq_item.get('question'):
                md += f"### {faq_item['question']}\n\n"
            if faq_item.get('answer'):
                md += f"{faq_item['answer']}\n\n"

    return md.strip()


def render_guide_news_article(data: dict) -> str:
    """
    Renderer for Guide and News articles (headings_content structure)
    """
    md = ""

    # 1. Title
    if data.get('title'):
        md += f"# {data['title']}\n\n"

    # 2. Introduction
    intro = data.get('introduction', {})

    if intro.get('teaser'):
        md += f"{intro['teaser']}\n\n"

    if intro.get('nlp_answer'):
        md += f"{intro['nlp_answer']}\n\n"

    if intro.get('extended_answer'):
        md += f"{intro['extended_answer']}\n\n"

    if intro.get('hook2'):
        md += f"{intro['hook2']}\n\n"

    # 3. Headings Content (main content for guide/news)
    headings_content = data.get('headings_content', {})

    # Handle nested structure: headings_content.description.{items}
    if 'description' in headings_content:
        content_dict = headings_content['description']

        for heading_key, heading_data in content_dict.items():
            if isinstance(heading_data, dict):
                # Check if there's a 'heading' field, otherwise use the key
                heading = heading_data.get('heading', heading_key)
                paragraph = heading_data.get('paragraph')

                # Always create the heading
                md += f"## {heading}\n\n"

                # Add paragraph content if it exists
                if paragraph:
                    # Temporarily disable formatting to debug
                    md += f"{paragraph}\n\n"
            elif isinstance(heading_data, str):
                # Direct string content
                md += f"## {heading_key}\n\n"
                md += f"{heading_data}\n\n"

    # Handle direct structure: headings_content.{items}
    else:
        for key, content in headings_content.items():
            if key in ['description', 'template']:
                continue

            if isinstance(content, dict):
                heading = content.get('heading', key)
                paragraph = content.get('paragraph')

                if heading:
                    md += f"## {heading}\n\n"

                if paragraph:
                    md += f"{paragraph}\n\n"
            elif isinstance(content, str):
                md += f"## {key}\n\n"
                md += f"{content}\n\n"

    # 4. Conclusion
    conclusion = data.get('conclusion', {})
    if conclusion:
        md += "## Conclusion\n\n"

        if conclusion.get('summary'):
            md += f"{conclusion['summary']}\n\n"

        if conclusion.get('closing_sentence'):
            md += f"{conclusion['closing_sentence']}\n\n"

    # 5. FAQ
    if data.get('faq'):
        md += "## Questions Fréquentes\n\n"

        if data.get('faq_description'):
            md += f"{data['faq_description']}\n\n"

        for faq_item in data['faq']:
            if faq_item.get('question'):
                md += f"### {faq_item['question']}\n\n"
            if faq_item.get('answer'):
                md += f"{faq_item['answer']}\n\n"

    return md.strip()


def render_report_to_markdown(data: dict) -> str:
    """
    Main renderer that dispatches to the appropriate type-specific renderer
    """
    # Try to detect post_type from metadata if available
    post_type = None

    # Method 1: Look for post_type in the data itself
    if 'post_type' in data:
        post_type = data['post_type']

    # Method 2: Look for post_type in metadata
    elif 'metadata' in data and isinstance(data['metadata'], dict):
        post_type = data['metadata'].get('post_type')

    # Method 3: Auto-detect based on structure
    elif not post_type:
        if 'comparisons' in data:
            post_type = 'Affiliate'
        elif 'headings_content' in data:
            post_type = 'Guide'  # Guide and News use same structure
        else:
            post_type = 'Guide'  # Default fallback

    print(f"[DEBUG] Detected/Using post_type: {post_type}")

    # Dispatch to appropriate renderer
    if post_type == 'Affiliate':
        return render_affiliate_article(data)
    elif post_type in ['Guide', 'News']:
        return render_guide_news_article(data)
    else:
        print(f"[WARNING] Unknown post_type '{post_type}', defaulting to Guide/News renderer")
        return render_guide_news_article(data)


def markdown_to_html(markdown_content: str) -> str:
    return markdown.markdown(markdown_content)


def post_article_to_wordpress(article_json: dict, jwt_token: str, html: str = None) -> str:
    post_url = "https://stuffgaming.fr/wp-json/wp/v2/posts"
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Content-Type": "application/json"
    }

    payload = {
        "title": article_json["title"],
        "slug": slugify(article_json["title"]),
        "content": html or "",
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
        print(f"[ERROR] ❌ Échec de création de l'article : {e}")
        if res is not None:
            print(f"[DEBUG] ↪ Status: {res.status_code}")
            print(f"[DEBUG] ↪ Response: {res.text}")
        return None


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
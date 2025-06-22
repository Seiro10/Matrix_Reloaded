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
# ADD THIS LINE:
from typing import List


def render_structured_content_blocks(blocks: List) -> str:
    """Convert structured content blocks to markdown."""
    md = ""

    for block in blocks:
        block_type = block.get('type', 'paragraph')
        content = block.get('content', '')

        if block_type == "paragraph":
            md += f"{content}\n\n"

        elif block_type == "bullet_list":
            if content:
                md += f"{content}\n"
            items = block.get('items', [])
            for item in items:
                md += f"• {item}\n"
            md += "\n"

        elif block_type == "numbered_list":
            if content:
                md += f"{content}\n"
            items = block.get('items', [])
            for i, item in enumerate(items, 1):
                md += f"{i}. {item}\n"
            md += "\n"

        elif block_type == "table":
            if content:
                md += f"{content}\n"
            table_data = block.get('table_data', [])
            if table_data:
                # Add table headers if first row
                if len(table_data) > 0:
                    md += "| " + " | ".join(table_data[0]) + " |\n"
                    md += "|" + "---|" * len(table_data[0]) + "\n"
                    for row in table_data[1:]:
                        md += "| " + " | ".join(row) + " |\n"
            md += "\n"

        elif block_type == "pros_cons":
            if content:
                md += f"{content}\n"
            pros = block.get('pros', [])
            cons = block.get('cons', [])

            if pros:
                md += "**Avantages :**\n"
                for pro in pros:
                    md += f"• ✅ {pro}\n"
                md += "\n"

            if cons:
                md += "**Inconvénients :**\n"
                for con in cons:
                    md += f"• ❌ {con}\n"
                md += "\n"

    return md


def format_text_with_structure(text: str) -> str:
    """
    Convert structured text patterns to proper markdown formatting
    """
    if not text:
        return text

    # Don't process text that's already well-formatted or doesn't need formatting
    if len(text) < 50:  # Short text probably doesn't need complex formatting
        return text

    # First, fix any malformed tables
    text = fix_markdown_tables(text)

    # Convert numbered lists: "1. Item" to proper markdown
    text = re.sub(r'^(\d+)\.\s*([^\n]+)', r'1. \2', text, flags=re.MULTILINE)

    # Convert bullet points: "- Item" to proper markdown
    text = re.sub(r'^-\s*([^\n]+)', r'- \1', text, flags=re.MULTILINE)

    # Convert bullet points: "• Item" to markdown
    text = re.sub(r'^•\s*([^\n]+)', r'- \1', text, flags=re.MULTILINE)

    # Convert checkmarks to emojis
    text = re.sub(r'^✅\s*([^\n]+)', r'- ✅ \1', text, flags=re.MULTILINE)
    text = re.sub(r'^❌\s*([^\n]+)', r'- ❌ \1', text, flags=re.MULTILINE)

    # Handle **Avantages :** and **Inconvénients :** sections
    text = re.sub(r'\*\*Avantages\s*:\*\*', r'\n**Avantages :**', text)
    text = re.sub(r'\*\*Inconvénients\s*:\*\*', r'\n**Inconvénients :**', text)

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
        md += f"{format_text_with_structure(intro['teaser'])}\n\n"

    if intro.get('nlp_answer'):
        md += f"{format_text_with_structure(intro['nlp_answer'])}\n\n"

    if intro.get('extended_answer'):
        md += f"{format_text_with_structure(intro['extended_answer'])}\n\n"

    if intro.get('hook2'):
        md += f"{format_text_with_structure(intro['hook2'])}\n\n"

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
                structure_aids = heading_data.get('structure_aids')

                # Always create the heading
                md += f"## {heading}\n\n"

                # Add paragraph content if it exists
                if paragraph:
                    md += f"{format_text_with_structure(paragraph)}\n\n"

                # Add structure aids (lists, tables, etc.)
                if structure_aids:
                    md += f"{format_text_with_structure(structure_aids)}\n\n"

            elif isinstance(heading_data, str):
                # Direct string content
                md += f"## {heading_key}\n\n"
                md += f"{format_text_with_structure(heading_data)}\n\n"

    # Handle direct structure: headings_content.{items}
    else:
        for key, content in headings_content.items():
            if key in ['description', 'template']:
                continue

            if isinstance(content, dict):
                heading = content.get('heading', key)
                paragraph = content.get('paragraph')
                structure_aids = content.get('structure_aids')

                if heading:
                    md += f"## {heading}\n\n"

                if paragraph:
                    md += f"{format_text_with_structure(paragraph)}\n\n"

                if structure_aids:
                    md += f"{format_text_with_structure(structure_aids)}\n\n"

            elif isinstance(content, str):
                md += f"## {key}\n\n"
                md += f"{format_text_with_structure(content)}\n\n"

    # 4. Conclusion
    conclusion = data.get('conclusion', {})
    if conclusion:
        md += "## Conclusion\n\n"

        if conclusion.get('summary'):
            md += f"{format_text_with_structure(conclusion['summary'])}\n\n"

        if conclusion.get('closing_sentence'):
            md += f"{format_text_with_structure(conclusion['closing_sentence'])}\n\n"

    # 5. FAQ
    if data.get('faq'):
        md += "## Questions Fréquentes\n\n"

        if data.get('faq_description'):
            md += f"{format_text_with_structure(data['faq_description'])}\n\n"

        for faq_item in data['faq']:
            if faq_item.get('question'):
                md += f"### {faq_item['question']}\n\n"
            if faq_item.get('answer'):
                md += f"{format_text_with_structure(faq_item['answer'])}\n\n"

    return md.strip()


def render_structured_affiliate_article(data: dict) -> str:
    """Renderer for NEW structured Affiliate articles."""
    md = ""

    # Title
    if data.get('title'):
        md += f"# {data['title']}\n\n"

    # Introduction
    intro = data.get('introduction', {})
    if intro.get('blocks'):
        md += render_structured_content_blocks(intro['blocks'])

    # Comparisons
    for comparison in data.get('comparisons', []):
        product_title = comparison.get('title', '')
        product_name = comparison.get('product', '')

        if product_name:
            md += f"## {product_title}: {product_name}\n\n"
        else:
            md += f"## {product_title}\n\n"

        if comparison.get('description'):
            md += f"{comparison['description']}\n\n"

        # Render structured content blocks
        content_blocks = comparison.get('content_blocks', [])
        md += render_structured_content_blocks(content_blocks)

    # Notable mentions
    for mention in data.get('notable_mentions', []):
        md += f"## {mention.get('heading', 'Mention Spéciale')}\n\n"
        md += render_structured_content_blocks(mention.get('blocks', []))

    # Conclusion
    conclusion = data.get('conclusion', {})
    if conclusion:
        md += f"## {conclusion.get('heading', 'Conclusion')}\n\n"
        md += render_structured_content_blocks(conclusion.get('blocks', []))

    # FAQ (keep as before)
    if data.get('faq'):
        md += "## Questions Fréquentes\n\n"
        for faq_item in data['faq']:
            if faq_item.get('question'):
                md += f"### {faq_item['question']}\n\n"
            if faq_item.get('answer'):
                md += f"{faq_item['answer']}\n\n"

    return md.strip()


def render_structured_guide_news_article(data: dict) -> str:
    """Renderer for NEW structured Guide/News articles."""
    md = ""

    # Title
    if data.get('title'):
        md += f"# {data['title']}\n\n"

    # Introduction
    intro = data.get('introduction', {})
    if intro.get('blocks'):
        md += render_structured_content_blocks(intro['blocks'])

    # Main sections
    for section in data.get('main_sections', []):
        md += f"## {section.get('heading', '')}\n\n"
        md += render_structured_content_blocks(section.get('blocks', []))

    # Conclusion
    conclusion = data.get('conclusion', {})
    if conclusion:
        md += f"## {conclusion.get('heading', 'Conclusion')}\n\n"
        md += render_structured_content_blocks(conclusion.get('blocks', []))

    # FAQ
    if data.get('faq'):
        md += "## Questions Fréquentes\n\n"
        for faq_item in data['faq']:
            if faq_item.get('question'):
                md += f"### {faq_item['question']}\n\n"
            if faq_item.get('answer'):
                md += f"{faq_item['answer']}\n\n"

    return md.strip()


# MODIFY the existing render_report_to_markdown function (keep the same name!)
def render_report_to_markdown(data: dict) -> str:
    """
    Main renderer that dispatches to the appropriate type-specific renderer
    NOW SUPPORTS BOTH OLD AND NEW STRUCTURED FORMATS
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
            post_type = 'Guide'
        else:
            post_type = 'Guide'

    print(f"[DEBUG] Detected/Using post_type: {post_type}")

    # NEW: Check if this is the structured format
    if isinstance(data, dict):
        # Check for structured content blocks
        has_structured_content = False

        # Check in comparisons
        comparisons = data.get('comparisons', [])
        if comparisons and any('content_blocks' in comp for comp in comparisons):
            has_structured_content = True

        # Check in introduction/main_sections
        intro = data.get('introduction', {})
        main_sections = data.get('main_sections', [])
        if (isinstance(intro, dict) and 'blocks' in intro) or main_sections:
            has_structured_content = True

        if has_structured_content:
            print(f"[DEBUG] Using NEW structured renderer for {post_type}")
            if post_type == 'Affiliate':
                return render_structured_affiliate_article(data)
            else:
                return render_structured_guide_news_article(data)

    # Fallback to existing renderers for old format
    print(f"[DEBUG] Using EXISTING renderer for {post_type}")
    if post_type == 'Affiliate':
        return render_affiliate_article(data)  # YOUR ORIGINAL FUNCTION
    elif post_type in ['Guide', 'News']:
        return render_guide_news_article(data)  # YOUR ORIGINAL FUNCTION
    else:
        print(f"[WARNING] Unknown post_type '{post_type}', defaulting to Guide/News renderer")
        return render_guide_news_article(data)  # YOUR ORIGINAL FUNCTION

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


def fix_markdown_tables(text: str) -> str:
    """
    Fix malformed markdown tables by properly formatting them
    """
    if not text or '|' not in text:
        return text

    lines = text.split('\n')
    processed_lines = []
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        # Check if this looks like a table row (contains | and has content)
        if '|' in line and len(line.split('|')) >= 3:
            # Start processing table
            table_lines = []

            # Collect all consecutive table lines
            while i < len(lines) and '|' in lines[i]:
                table_line = lines[i].strip()
                if table_line:  # Skip empty lines
                    table_lines.append(table_line)
                i += 1

            if table_lines:
                # Process the table
                fixed_table = format_table_properly(table_lines)
                processed_lines.extend(fixed_table)
                processed_lines.append('')  # Add empty line after table

            # Don't increment i here since we already did it in the while loop
            continue
        else:
            processed_lines.append(line)
            i += 1

    return '\n'.join(processed_lines)


def format_table_properly(table_lines: list) -> list:
    """
    Format a list of table lines into proper markdown table format
    """
    if not table_lines:
        return []

    formatted_lines = []

    # Process first line as header
    first_line = table_lines[0]

    # Clean up the first line - remove multiple | at start/end
    first_line = re.sub(r'^\|+', '| ', first_line)
    first_line = re.sub(r'\|+$', ' |', first_line)

    # Split and clean columns
    columns = [col.strip() for col in first_line.split('|')[1:-1] if col.strip()]

    if not columns:
        return table_lines  # Return original if we can't parse

    # Create proper header
    header = '| ' + ' | '.join(columns) + ' |'
    formatted_lines.append(header)

    # Create separator
    separator = '|' + '---|' * len(columns) + '|'
    formatted_lines.append(separator)

    # Process remaining lines as data rows
    for line in table_lines[1:]:
        # Skip if this looks like a separator line already
        if '---' in line:
            continue

        # Clean up the line
        line = re.sub(r'^\|+', '| ', line)
        line = re.sub(r'\|+$', ' |', line)

        # Split and clean columns
        row_columns = [col.strip() for col in line.split('|')[1:-1]]

        # Ensure we have the right number of columns
        while len(row_columns) < len(columns):
            row_columns.append('')

        # Truncate if too many columns
        row_columns = row_columns[:len(columns)]

        # Create proper row
        row = '| ' + ' | '.join(row_columns) + ' |'
        formatted_lines.append(row)

    return formatted_lines
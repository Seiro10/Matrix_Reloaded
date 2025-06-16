import os
from langchain_anthropic import ChatAnthropic
from bs4 import BeautifulSoup
from typing import Dict, Any

from app.agents.state import ArticleRewriterState
from app.agents.utils.html_processor import HTMLProcessor
from app.config import settings


def download_article_node(state: ArticleRewriterState) -> ArticleRewriterState:
    """Download the original article"""
    print(f"[NODE] Downloading article from: {state['article_url']}")

    try:
        import requests
        response = requests.get(state["article_url"], timeout=30)
        response.raise_for_status()

        # Save to temp file
        temp_path = f"{settings.temp_dir}/temp_article.html"
        os.makedirs(settings.temp_dir, exist_ok=True)

        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(response.text)

        state["original_html"] = response.text
        state["temp_file_path"] = temp_path
        state["status"] = "article_downloaded"

        print("[NODE] ✅ Article downloaded successfully")

    except Exception as e:
        state["error"] = f"Failed to download article: {str(e)}"
        state["status"] = "error"
        print(f"[NODE] ❌ Download failed: {e}")

    return state


def extract_slug_node(state: ArticleRewriterState) -> ArticleRewriterState:
    """Extract slug from article URL"""
    print(f"[NODE] Extracting slug from URL: {state['article_url']}")

    try:
        from urllib.parse import urlparse
        path = urlparse(state["article_url"]).path
        parts = [p for p in path.strip("/").split("/") if p]
        state["slug"] = parts[-1] if parts else None

        print(f"[NODE] ✅ Extracted slug: {state['slug']}")

    except Exception as e:
        state["error"] = f"Failed to extract slug: {str(e)}"
        state["status"] = "error"
        print(f"[NODE] ❌ Slug extraction failed: {e}")

    return state


def authenticate_wordpress_node(state: ArticleRewriterState) -> ArticleRewriterState:
    """Authenticate with WordPress"""
    print("[NODE] Authenticating with WordPress")

    try:
        from app.agents.utils.wordpress_client import WordPressClient
        wp_client = WordPressClient()
        token = wp_client.get_jwt_token(settings.username_wp, settings.password_wp)

        if not token:
            raise Exception("Failed to get JWT token")

        state["jwt_token"] = token
        print("[NODE] ✅ WordPress authentication successful")

    except Exception as e:
        state["error"] = f"WordPress authentication failed: {str(e)}"
        state["status"] = "error"
        print(f"[NODE] ❌ WordPress auth failed: {e}")

    return state


def get_post_id_node(state: ArticleRewriterState) -> ArticleRewriterState:
    """Get WordPress post ID from slug"""
    print(f"[NODE] Getting post ID for slug: {state['slug']}")

    try:
        from app.agents.utils.wordpress_client import WordPressClient
        wp_client = WordPressClient()
        post_id = wp_client.get_post_id_from_slug(state["slug"], state["jwt_token"])

        if not post_id:
            raise Exception(f"No post found with slug: {state['slug']}")

        state["post_id"] = post_id
        print(f"[NODE] ✅ Found post ID: {post_id}")

    except Exception as e:
        state["error"] = f"Failed to get post ID: {str(e)}"
        state["status"] = "error"
        print(f"[NODE] ❌ Post ID lookup failed: {e}")

    return state


def process_html_blocks_node(state: ArticleRewriterState) -> ArticleRewriterState:
    """Extract and process HTML blocks"""
    print("[NODE] Processing HTML blocks")

    try:
        processor = HTMLProcessor()
        blocks = processor.extract_html_blocks(state["original_html"])

        state["html_blocks"] = blocks
        print(f"[NODE] ✅ Extracted {len(blocks)} HTML blocks")

    except Exception as e:
        state["error"] = f"Failed to process HTML blocks: {str(e)}"
        state["status"] = "error"
        print(f"[NODE] ❌ HTML block processing failed: {e}")

    return state


def update_blocks_node(state: ArticleRewriterState) -> ArticleRewriterState:
    """Update blocks based on additional content"""
    print("[NODE] Updating blocks with new content")

    try:
        updated_blocks = []

        for block in state["html_blocks"]:
            updated_block = update_block_if_needed(
                block,
                state["subject"],
                state["additional_content"]
            )
            updated_blocks.append(updated_block)

        state["updated_blocks"] = updated_blocks
        print(f"[NODE] ✅ Updated {len(updated_blocks)} blocks")

    except Exception as e:
        state["error"] = f"Failed to update blocks: {str(e)}"
        state["status"] = "error"
        print(f"[NODE] ❌ Block update failed: {e}")

    return state


def reconstruct_article_node(state: ArticleRewriterState) -> ArticleRewriterState:
    """Reconstruct the article from updated blocks"""
    print("[NODE] Reconstructing article")

    try:
        processor = HTMLProcessor()
        reconstructed = processor.reconstruct_blocks(state["updated_blocks"])

        state["reconstructed_html"] = reconstructed
        print("[NODE] ✅ Article reconstructed")

    except Exception as e:
        state["error"] = f"Failed to reconstruct article: {str(e)}"
        state["status"] = "error"
        print(f"[NODE] ❌ Article reconstruction failed: {e}")

    return state


def diagnose_missing_sections_node(state: ArticleRewriterState) -> ArticleRewriterState:
    """Diagnose what sections are missing"""
    print("[NODE] Diagnosing missing sections")

    try:
        diagnostic = diagnose_missing_sections(
            state["subject"],
            state["reconstructed_html"],
            state["additional_content"]
        )

        state["diagnostic"] = diagnostic
        print("[NODE] ✅ Diagnostic completed")

    except Exception as e:
        state["error"] = f"Failed to diagnose sections: {str(e)}"
        state["status"] = "error"
        print(f"[NODE] ❌ Diagnostic failed: {e}")

    return state


def generate_new_sections_node(state: ArticleRewriterState) -> ArticleRewriterState:
    """Generate new sections based on diagnostic"""
    print("[NODE] Generating new sections")

    try:
        generated = generate_sections(
            state["subject"],
            state["diagnostic"],
            state["additional_content"]
        )

        state["generated_sections"] = generated
        print("[NODE] ✅ New sections generated")

    except Exception as e:
        state["error"] = f"Failed to generate sections: {str(e)}"
        state["status"] = "error"
        print(f"[NODE] ❌ Section generation failed: {e}")

    return state


def merge_final_article_node(state: ArticleRewriterState) -> ArticleRewriterState:
    """Merge everything into final article"""
    print("[NODE] Merging final article")

    try:
        final_html = merge_final_article(
            state["subject"],
            state["reconstructed_html"],
            state["generated_sections"]
        )

        # Clean the HTML
        processor = HTMLProcessor()
        final_html = processor.clean_all_content(final_html)

        state["final_html"] = final_html
        state["status"] = "content_ready"
        print("[NODE] ✅ Final article merged and cleaned")

    except Exception as e:
        state["error"] = f"Failed to merge final article: {str(e)}"
        state["status"] = "error"
        print(f"[NODE] ❌ Final merge failed: {e}")

    return state


def publish_to_wordpress_node(state: ArticleRewriterState) -> ArticleRewriterState:
    """Publish the final article to WordPress"""
    print(f"[NODE] Publishing to WordPress (Post ID: {state['post_id']})")

    try:
        # Save to temp file
        output_path = f"{settings.generated_dir}/final_article.txt"
        os.makedirs(settings.generated_dir, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(state["final_html"])

        # Update WordPress
        from app.agents.utils.wordpress_client import WordPressClient
        wp_client = WordPressClient()
        success = wp_client.update_wordpress_article(
            state["post_id"],
            output_path,
            state["jwt_token"]
        )

        if success:
            state["status"] = "completed"
            print(f"[NODE] ✅ Article published successfully (ID: {state['post_id']})")
        else:
            raise Exception("WordPress update failed")

    except Exception as e:
        state["error"] = f"Failed to publish to WordPress: {str(e)}"
        state["status"] = "error"
        print(f"[NODE] ❌ WordPress publish failed: {e}")

    return state


# GPT Helper Functions (adapted from your original code)

def update_block_if_needed(block, subject, additional_content):
    """Update a single block if needed using GPT"""
    title = block['title']
    content_html = "\n".join([str(e) for e in block['content']])
    title_text = title.get_text() if title else "Sans titre"

    prompt = [
        {
            "role": "system",
            "content": """
### ROLE
You're a French world-class copywriter specializing in video games. Your job is to update and improve article sections based on additional content provided.

### GOAL
- Identify if a section is:
  - VALID (still accurate and aligned with the additional content)
  - TO BE UPDATED (partially outdated or missing context)
  - OUTDATED (no longer valid and must be rewritten)

### INSTRUCTIONS
- If VALID → respond `STATUS: VALID` and explain briefly why.
- If TO BE UPDATED → respond `STATUS: TO BE UPDATED` and give a corrected version (HTML).
- If OUTDATED → respond `STATUS: OUTDATED` and give a rewritten version (HTML).
- Use <p>, <ul>, <li>, <strong>, <em>, etc. No <div>, no inline styles.
- Write in French.

### TECHNICAL LIMITATIONS
- Never use long dashes (—). Replace them with a comma, semicolon or period.
- Never exceed three lines per paragraph.
"""
        },
        {
            "role": "user",
            "content": f"""
Sujet : {subject}
Titre : {title_text}

Contenu HTML :
{content_html}

Contenu additionnel à intégrer :
{additional_content}

Évalue cette section et mets-la à jour si besoin.
"""
        }
    ]

    try:
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            messages=prompt,
            temperature=0.4,
            max_tokens=1800
        )
        result = response.content[0].text.strip()

        if result.startswith("STATUS: VALID"):
            return block
        elif result.startswith("STATUS: TO BE UPDATED") or result.startswith("STATUS: OUTDATED"):
            html_start = result.split("\n", 1)[1].strip()
            soup = BeautifulSoup(html_start, "html.parser")
            updated_block = {
                "title": title,
                "content": list(soup.contents)
            }
            return updated_block
        else:
            return block

    except Exception as e:
        print(f"[ERROR] GPT block update failed: {e}")
        return block


def diagnose_missing_sections(subject, original_html, additional_content):
    """Diagnose missing sections using GPT"""
    prompt = [
        {
            "role": "system",
            "content": """
### ROLE
Tu es un éditeur de contenu. Analyse un article et du contenu additionnel pour identifier les sujets pertinents qui ne sont pas encore couverts.

### GOAL
Génère entre 1 et 3 nouvelles sections pertinentes à ajouter à l'article. Chaque section doit avoir :
- Un titre sous forme de balise <h2>
- Une courte description en une phrase (maximum 25 mots)

### GUIDELINES
- Ne suggère pas de doublons
- Priorise les apports d'expérience non couverts
- Reste simple et informatif

### TECHNICAL LIMITATIONS
- Utilise uniquement : <h2>, <p>
- N'utilise jamais de tirets longs (—)
- Ne dépasse jamais trois lignes par paragraphe
"""
        },
        {
            "role": "user",
            "content": f"""
Sujet : {subject}

Article HTML :
{original_html}

Contenu additionnel :
{additional_content}
"""
        }
    ]

    try:
        # CHANGE from openai to anthropic:
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            messages=prompt,
            max_tokens=1000
        )
        return response.content[0].text.strip()
    except Exception as e:
        print(f"[ERROR] GPT diagnostic failed: {e}")
        return ""


def generate_sections(subject, diagnostic, additional_content):
    """Generate new sections using GPT"""
    prompt = [
        {
            "role": "system",
            "content": """
### ROLE
Tu es un joueur passionné qui partage ses avis et expériences sur les jeux vidéo.

### GOAL
Écrire des paragraphes immersifs et personnels en français (100 mots minimum).

### GUIDELINES
- Utilise la première personne
- Adopte un ton naturel, humain
- Reste fluide : phrases simples

### TECHNICAL LIMITATIONS
- HTML only: <h2>, <h3>, <p>, <ul>, <li>, <strong>, <em>, <blockquote>
- N'utilise jamais de tirets longs (—)
- Ne dépasse jamais trois lignes par paragraphe
"""
        },
        {
            "role": "user",
            "content": f"""
Sujet : {subject}

Sections à créer :
{diagnostic}

Contenu additionnel :
{additional_content}
"""
        }
    ]

    try:
        # CHANGE from openai to anthropic:
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            messages=prompt,
            max_tokens=3000,
            temperature=1,
            # Note: Anthropic doesn't have top_p, frequency_penalty, presence_penalty
        )
        return response.content[0].text.strip()
    except Exception as e:
        print(f"[ERROR] GPT section generation failed: {e}")
        return ""


def merge_final_article(subject, reconstructed_html, generated_sections):
    """Merge everything into final article using GPT"""
    prompt = [
        {
            "role": "system",
            "content": """
### ROLE
You are a senior French web editor specialized in video game journalism.

### GOAL
Merge new information into an existing article without duplicating ideas.
Analyze the original structure and enrich it with new content by injecting generated paragraphs directly into existing sections when relevant.

### GUIDELINES
- Use the updated article as the foundation
- Integrate new content as extra paragraphs inside existing sections when relevant
- Do not repeat or rephrase what is already covered
- Respect logical flow, tone, and style
- Update references to years (e.g., 2024 to 2025) if content is meant to be current

### STYLE RULES
- Write in fluent, direct French
- Avoid fluff, clichés, and redundant transitions
- Short paragraphs (3 lines max), without long dashes
- Never exceed three lines per paragraph

### TECHNICAL LIMITATIONS
- Use only: <h2>, <h3>, <p>, <ul>, <li>, <strong>, <em>, <blockquote>, <img>, <a>
- Do NOT use <html>, <body>, <head>, <style> or inline styles
- Return only clean, merged HTML

### OUTPUT
Return only clean, merged HTML. No headers, no extra output, without long dashes.
"""
        },
        {
            "role": "user",
            "content": f"""
Sujet : {subject}

Article révisé :
{reconstructed_html}

Nouvelles sections générées à intégrer :
{generated_sections}
"""
        }
    ]

    try:
        # CHANGE from openai to anthropic:
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            messages=prompt,
            max_tokens=8000,
            temperature=0.5
        )
        return response.content[0].text.strip()
    except Exception as e:
        print(f"[ERROR] GPT merge failed: {e}")
        return reconstructed_html + "\n\n" + generated_sections
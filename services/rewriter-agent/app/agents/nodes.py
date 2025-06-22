import os
from langchain_anthropic import ChatAnthropic
from bs4 import BeautifulSoup, Tag
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

        # Convertir tous les tags BeautifulSoup en string propre
        for block in blocks:
            block["title"] = str(block["title"]) if block["title"] else ""
            block["content"] = [str(e) for e in block["content"]]

        state["html_blocks"] = blocks

        print(f"[NODE] ✅ Extracted {len(blocks)} HTML blocks")

    except Exception as e:
        state["error"] = f"Failed to process HTML blocks: {str(e)}"
        state["status"] = "error"
        print(f"[NODE] ❌ HTML block processing failed: {e}")

    return state


def update_blocks_node(state: ArticleRewriterState) -> ArticleRewriterState:
    """Update blocks based on additional content - EXACT logic from views2.py"""
    print("[NODE] Updating blocks with new content")

    try:
        updated_blocks = []

        for i, block in enumerate(state["html_blocks"]):
            block_title = "Sans titre"
            if block.get("title"):
                try:
                    # Tenter d'extraire le texte du titre HTML
                    soup = BeautifulSoup(block["title"], "html.parser")
                    block_title = soup.get_text(strip=True) or "Sans titre"
                except Exception:
                    block_title = "Sans titre"
            print(f"[DEBUG] Traitement du bloc {i + 1}/{len(state['html_blocks'])}: {block_title}")

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
        print("[DEBUG] ▶️ Preview reconstructed HTML:")
        print(state["reconstructed_html"][:1000])

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
    """Merge everything into final article - EXACT logic from views2.py"""
    print("[NODE] Merging final article")

    try:
        # First apply strip_duplicate_title_and_featured_image like Django does
        processor = HTMLProcessor()
        cleaned_reconstructed = processor.strip_duplicate_title_and_featured_image(state["reconstructed_html"])

        final_html = merge_final_article(
            state["subject"],
            cleaned_reconstructed,
            state["generated_sections"]
        )

        # Apply media cleaning pipeline like Django views2.py
        print("[DEBUG] ▶️ Applying media cleaning pipeline")
        soup_final = BeautifulSoup(final_html, "html.parser")
        soup_final = processor.clean_all_images(soup_final)
        soup_final = processor.simplify_youtube_embeds(soup_final)
        soup_final = processor.restore_youtube_iframes_from_rll_div(soup_final)
        final_html = str(soup_final)

        state["final_html"] = final_html
        state["status"] = "content_ready"
        print("[NODE] ✅ Final article merged and cleaned")

        # Debug output
        print(f"[DEBUG] Final HTML length: {len(final_html)} characters")
        print(f"[DEBUG] Final HTML preview: {final_html[:200]}...")

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


# Initialize Claude model
llm = ChatAnthropic(
    model="claude-3-5-sonnet-20241022",
    api_key=settings.anthropic_api_key,
    temperature=0.4,
    max_tokens=1800
)


def update_block_if_needed(block, subject, additional_content):
    """Update a single block if needed - EXACT format from views2.py with simpler prompt"""
    raw_title = block.get("title", "")
    try:
        title_text = BeautifulSoup(raw_title, "html.parser").get_text(strip=True) or "Sans titre"
    except Exception:
        title_text = "Sans titre"

    content_html = "\n".join(block["content"])

    # Simplified prompt to match exactly what works in Django
    prompt = f"""Tu es un expert en rédaction de jeux vidéo. Évalue cette section et réponds avec un des formats suivants UNIQUEMENT :

STATUS: VALID
[explication courte]

OU

STATUS: TO BE UPDATED
[nouveau HTML]

OU

STATUS: OUTDATED  
[nouveau HTML]

Section à évaluer :
Titre: {title_text}
Contenu: {content_html}

Contexte additionnel: {additional_content}

Sujet: {subject}"""

    try:
        response = llm.invoke(prompt)
        result = response.content.strip()
        print(f"[GPT] Bloc '{title_text}' ➤ {result[:80]}...")

        if "STATUS: VALID" in result:
            return block

        elif "STATUS: TO BE UPDATED" in result or "STATUS: OUTDATED" in result:
            # Extract HTML portion
            lines = result.split('\n')
            html_content = ""
            found_status = False

            for line in lines:
                if "STATUS:" in line:
                    found_status = True
                    continue
                if found_status and line.strip():
                    if '<' in line or html_content:
                        html_content += line + '\n'

            html_content = html_content.strip()

            if html_content and '<' in html_content:
                soup = BeautifulSoup(html_content, "html.parser")
                updated_block = {
                    "title": raw_title,  # Keep original HTML title as str
                    "content": [str(e) for e in soup.contents if isinstance(e, Tag)]
                }
                print(f"[DEBUG] Successfully updated block: {title_text}")
                return updated_block
            else:
                print(f"[WARNING] No valid HTML found for: {title_text}")
                return block
        else:
            print(f"[WARNING] No STATUS found in response for: {title_text}")
            return block

    except Exception as e:
        print(f"[ERROR] ChatAnthropic block update failed: {e}")
        return block


def diagnose_missing_sections(subject, original_html, additional_content):
    """Diagnose missing sections - EXACT format from views2.py"""
    prompt = [
        {
            "role": "system",
            "content": """
### ROLE
Tu es un éditeur de contenu. Ton rôle est d'analyser un article déjà rédigé et un transcript brut afin d'identifier les sujets pertinents qui ne sont pas encore couverts.

### GOAL
Génère entre 1 et 3 nouvelles sections pertinentes à ajouter à l'article. Chaque section doit avoir :
- Un titre sous forme de balise <h2>
- Une courte description en une phrase (maximum 25 mots) résumant le contenu attendu

### GUIDELINES
- Ne suggère pas de doublons : les thèmes déjà traités dans l'article ne doivent pas être répétés.
- Priorise les apports d'expérience ou d'angle personnel non couverts.
- Reste simple et informatif : ne génère pas de contenu ou de paragraphe.

### TECHNICAL LIMITATIONS
- Utilise uniquement les balises HTML suivantes : <h2>, <p>
- Ne génère rien d'autre (pas d'explication ou de commentaire)
- N'utilise jamais de tirets longs (—). Remplace-les par une virgule, un point-virgule ou un point selon le contexte.
- Ne dépasse jamais trois lignes par paragraphe. Coupe les idées longues en plusieurs blocs plus courts.
"""
        },
        {
            "role": "user",
            "content": f"""
Sujet : {subject}

Article HTML :
{original_html}

Transcript vidéo :
{additional_content}
"""
        }
    ]

    try:
        response = llm.invoke(prompt)
        return response.content.strip()
    except Exception as e:
        print(f"[ERROR] ChatAnthropic diagnostic failed: {e}")
        return ""


def generate_sections(subject, diagnostic, additional_content):
    """Generate new sections - EXACT format from views2.py"""
    prompt = [
        {
            "role": "system",
            "content": """
### ROLE
Tu es un joueur passionné qui partage ses avis et expériences sur les jeux vidéo de manière naturelle, mais claire.

### GOAL
Écrire des paragraphes immersifs et personnels en français (100 mots minimum), à partir de ton expérience de jeu.

### GUIDELINES
- Utilise la première personne : partage tes ressentis, tes doutes, tes frustrations ou tes moments marquants.
- Adopte un ton naturel, humain : comme si tu écrivais à un ami joueur, sans jargon marketing ni langue de bois.
- Évite les textes trop lisses ou trop formels : garde un peu d'hésitation, de spontanéité.
- Reste fluide : phrases simples, quelques respirations, mais pas trop relâché.
- Tu peux inclure des interjections ou des remarques personnelles (ex. : "honnêtement, j'étais paumé", "franchement, j'ai galéré"), mais modérément.

### STYLE
- Naturel > structuré
- Ton personnel, mais pas familier ou vulgaire
- Un peu de style rédactionnel, sans être encyclopédique
- Fragments de phrases ou contradictions légères bienvenus

### TECHNICAL LIMITATIONS
- HTML only: <h2>, <h3>, <p>, <ul>, <li>, <strong>, <em>, <blockquote>, <img>, <a>
- Une seule section par titre
- N'utilise jamais de tirets longs (—). Remplace-les par une virgule, un point-virgule ou un point selon le contexte.
- Ne dépasse jamais trois lignes par paragraphe. Coupe les idées longues en plusieurs blocs plus courts.
"""
        },
        {
            "role": "user",
            "content": f"""
Sujet : {subject}

Sections à créer :
{diagnostic}

Transcript :
{additional_content}
"""
        }
    ]

    try:
        # Use higher temperature and other parameters like views2.py
        section_llm = ChatAnthropic(
            model="claude-3-5-sonnet-20241022",
            api_key=settings.anthropic_api_key,
            temperature=1,
            max_tokens=3000
        )
        response = section_llm.invoke(prompt)
        return response.content.strip()
    except Exception as e:
        print(f"[ERROR] ChatAnthropic section generation failed: {e}")
        return ""


def merge_final_article(subject, reconstructed_html, generated_sections):
    """Merge everything into final article - EXACT format from views2.py"""
    prompt = [
        {
            "role": "system",
            "content": """
### ROLE
You are a senior French web editor specialized in video game journalism.

### GOAL
Your job is to **merge new information into an existing article** (already revised) without duplicating ideas.  
You must analyze the original structure and enrich it with **new content**, especially by **injecting generated paragraphs directly into existing sections** when relevant.

### GUIDELINES
- Use the updated article as the foundation.
- Carefully read the generated sections. If a generated section fits an existing section's topic, **integrate the new content as extra paragraphs inside that section.**
- Do not repeat or rephrase what is already covered.
- Respect logical flow, tone, and style of the original article.
- You may slightly rewrite paragraphs if it helps integrate the new information more smoothly.
- Update all references to years (e.g., 2024) to reflect the current year (2025) if the content is meant to be up to date.

### STYLE RULES
- Write in fluent, direct **French**.
- Avoid fluff, clichés, and redundant transitions.
- Never use names, brands, or YouTube references.
- Short paragraphs (3 lines max.), without long dashes.
- Never exceed three lines per paragraph. Cut long ideas into several shorter blocks.

### TECHNICAL LIMITATIONS
- Use only the following HTML tags: <h2>, <h3>, <p>, <ul>, <li>, <strong>, <em>, <blockquote>, <img>, <a>
- Do NOT use <html>, <body>, <head>, <style> or inline styles.
- Do not return any explanation or comment.
- Do not add meta-commentary like "[Continue...]" or "[Le reste du contenu...]" or "[Suite du contenu...]"
- Return ONLY the complete merged HTML content, nothing else.

### OUTPUT
Return only clean, merged HTML. No headers, no extra output, no commentary, without long dashes.
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
        # Use specific parameters like views2.py
        merge_llm = ChatAnthropic(
            model="claude-3-5-sonnet-20241022",
            api_key=settings.anthropic_api_key,
            temperature=0.5,
            max_tokens=8000
        )
        response = merge_llm.invoke(prompt)
        result = response.content.strip()

        # Remove any meta-commentary that might have been added
        if "[" in result and "]" in result:
            import re
            # Remove lines with meta-commentary
            lines = result.split('\n')
            cleaned_lines = []
            for line in lines:
                # Skip lines that contain meta-commentary in brackets
                if not re.search(r'\[.*\]', line.strip()):
                    cleaned_lines.append(line)
                else:
                    print(f"[DEBUG] Removing meta-commentary: {line.strip()}")
            result = '\n'.join(cleaned_lines)

        return result
    except Exception as e:
        print(f"[ERROR] ChatAnthropic merge failed: {e}")
        return reconstructed_html + "\n\n" + generated_sections
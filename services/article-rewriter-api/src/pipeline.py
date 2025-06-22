import os
import requests
import json
from bs4 import BeautifulSoup, Tag
from urllib.parse import urlparse
from dotenv import load_dotenv

from .utils import (
    extract_html_blocks, reconstruct_blocks, load_html_file,
    clean_all_images, simplify_youtube_embeds, restore_youtube_iframes_from_rll_div,
    get_jwt_token, extract_slug_from_url, get_post_id_from_slug,
    update_wordpress_article, strip_duplicate_title_and_featured_image
)
from .gpt_operations import (
    update_block_if_needed, diagnose_missing_sections,
    generate_sections, merge_final_article
)

load_dotenv()


def update_blog_article_pipeline(data):
    """
    Main pipeline function adapted from views2.py
    """
    try:
        article_url = data.get("article_url")
        subject = data.get("subject")
        additional_content = data.get("additional_content", "")

        if not article_url or not subject:
            return {'error': 'Données manquantes (article_url ou subject)'}

        print(f"[PIPELINE] URL: {article_url}, Sujet: {subject}")

        # 1. Télécharger l'article
        res = requests.get(article_url)
        if res.status_code != 200:
            return {'error': "Impossible de télécharger l'article"}

        existing_html = res.text
        with open("temp_article_pipeline.html", "w", encoding="utf-8") as f:
            f.write(existing_html)
        print("[DEBUG] Étape 1 : Article téléchargé")

        # 2. Mémoire centrale
        memory = {
            "subject": subject,
            "additional_content": additional_content,
            "original_html": existing_html,
            "diagnostic": "",
            "generated_sections": "",
            "reconstructed_html": "",
            "final_article": ""
        }

        # 3. Pipeline
        print("[DEBUG] ▶️ Étape 3.1 : Reconstruction HTML depuis blocs")
        memory["reconstructed_html"] = update_and_reconstruct_article(
            "temp_article_pipeline.html",
            subject,
            additional_content
        )

        # 3.2 Diagnostic + génération des nouvelles sections
        diagnose_missing_sections(memory)
        generate_sections(memory)

        # 3.3 Fusion intelligente via GPT
        print("[DEBUG] ▶️ Étape 3.3 : Fusion intelligente via GPT")
        memory["reconstructed_html"] = strip_duplicate_title_and_featured_image(memory["reconstructed_html"])
        merge_final_article(memory)

        if not memory["final_article"]:
            return {'error': 'Fusion échouée, article final vide.'}

        print("[DEBUG] ▶️ Étape 3.4 : Nettoyage HTML")
        soup_final = BeautifulSoup(memory["final_article"], "html.parser")
        soup_final = clean_all_images(soup_final)
        soup_final = simplify_youtube_embeds(soup_final)
        soup_final = restore_youtube_iframes_from_rll_div(soup_final)
        memory["final_article"] = str(soup_final)

        # 4. Logs
        os.makedirs("logs/memory_pipeline", exist_ok=True)
        for k, v in memory.items():
            with open(f"logs/memory_pipeline/{k}.txt", "w", encoding="utf-8") as f:
                f.write(str(v))
        print("[DEBUG] Étape 4 : Logs générés")

        # 5. Enregistrement local
        output_path = "./generated/updated_pipeline_article.txt"
        os.makedirs("generated", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(memory["final_article"])
        print("[DEBUG] Étape 5 : Article final sauvegardé localement")

        # 6. Upload vers WordPress
        print("[DEBUG] Étape 6 : Authentification WordPress")
        username = os.getenv("USERNAME_WP")
        password = os.getenv("PASSWORD_WP")
        jwt_token = get_jwt_token(username, password)

        if not jwt_token:
            return {'error': "Échec de l'authentification WordPress"}

        slug = extract_slug_from_url(article_url)
        post_id = get_post_id_from_slug(slug, jwt_token)

        if not post_id:
            return {'error': f"Article introuvable pour le slug '{slug}'"}

        success = update_wordpress_article(post_id, output_path, jwt_token)
        if not success:
            return {'error': "Échec de la mise à jour sur WordPress"}

        print(f"[DEBUG] ✅ Article publié sur WordPress (ID {post_id})")

        return {
            "message": f"✅ Article mis à jour avec succès sur WordPress (ID {post_id})",
            "updated_html": memory["final_article"],
            "post_id": post_id
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {'error': f'Erreur interne : {str(e)}'}


def update_and_reconstruct_article(filepath, subject, additional_content):
    """
    Update and reconstruct article from HTML blocks
    """
    html = load_html_file(filepath)
    blocks = extract_html_blocks(html)
    updated_blocks = []

    for block in blocks:
        title_text = "Sans titre"
        if block['title']:
            title_text = block['title'].get_text() if hasattr(block['title'], 'get_text') else 'Sans titre'

        print(f"[DEBUG] Traitement du bloc : {title_text}")
        updated_block = update_block_if_needed(block, subject, additional_content)
        updated_blocks.append(updated_block)

    return reconstruct_blocks(updated_blocks)
import os
import requests
import json
from bs4 import BeautifulSoup, Tag
from urllib.parse import urlparse
from dotenv import load_dotenv
import logging

from .utils import (
    extract_html_blocks, reconstruct_blocks, load_html_file,
    clean_all_images, simplify_youtube_embeds, restore_youtube_iframes_from_rll_div,
    get_jwt_token, extract_slug_from_url, get_post_id_from_slug,
    update_wordpress_article, strip_duplicate_title_and_featured_image
)
from .gpt_operations import (
    update_block_if_needed,
    diagnose_missing_sections,
    generate_sections,
    merge_final_article_structured
)

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def update_blog_article_pipeline(data):
    """
    Main pipeline function adapted from views2.py
    """
    try:
        logger.info("=== STARTING ARTICLE UPDATE PIPELINE ===")

        # Step 0: Extract and validate input
        article_url = data.get("article_url")
        subject = data.get("subject")
        additional_content = data.get("additional_content", "")

        logger.info(f"[STEP 0] Input validation:")
        logger.info(f"  - Article URL: {article_url}")
        logger.info(f"  - Subject: {subject}")
        logger.info(f"  - Additional content length: {len(additional_content)} chars")

        if not article_url or not subject:
            logger.error("[STEP 0] Missing required data")
            return {'error': 'Données manquantes (article_url ou subject)'}

        # Step 1: Download article
        logger.info("[STEP 1] Downloading article...")
        res = requests.get(article_url)
        logger.info(f"[STEP 1] HTTP Status: {res.status_code}")

        if res.status_code != 200:
            logger.error(f"[STEP 1] Failed to download article: {res.status_code}")
            return {'error': "Impossible de télécharger l'article"}

        existing_html = res.text
        logger.info(f"[STEP 1] Downloaded HTML length: {len(existing_html)} chars")

        with open("temp_article_pipeline.html", "w", encoding="utf-8") as f:
            f.write(existing_html)
        logger.info("[STEP 1] ✅ Article downloaded and saved")

        # Step 2: Initialize memory
        logger.info("[STEP 2] Initializing memory...")
        memory = {
            "subject": subject,
            "additional_content": additional_content,
            "original_html": existing_html,
            "diagnostic": "",
            "generated_sections": "",
            "reconstructed_html": "",
            "final_article": ""
        }
        logger.info("[STEP 2] ✅ Memory initialized")

        # Step 3.1: Update and reconstruct article
        logger.info("[STEP 3.1] Starting article reconstruction...")
        memory["reconstructed_html"] = update_and_reconstruct_article(
            "temp_article_pipeline.html",
            subject,
            additional_content
        )
        logger.info(f"[STEP 3.1] ✅ Reconstructed HTML length: {len(memory['reconstructed_html'])} chars")

        # Step 3.2: Diagnose missing sections
        logger.info("[STEP 3.2] Diagnosing missing sections...")
        diagnose_missing_sections(memory)
        logger.info(f"[STEP 3.2] ✅ Diagnostic length: {len(memory['diagnostic'])} chars")
        logger.info(f"[STEP 3.2] Diagnostic preview: {memory['diagnostic'][:200]}...")

        # Step 3.3: Generate new sections
        logger.info("[STEP 3.3] Generating new sections...")
        generate_sections(memory)
        logger.info(f"[STEP 3.3] ✅ Generated sections length: {len(memory['generated_sections'])} chars")

        # Step 3.4: Strip duplicate content
        logger.info("[STEP 3.4] Cleaning duplicate content...")
        memory["reconstructed_html"] = strip_duplicate_title_and_featured_image(memory["reconstructed_html"])
        logger.info(f"[STEP 3.4] ✅ Cleaned HTML length: {len(memory['reconstructed_html'])} chars")

        # Step 3.5: Merge final article
        logger.info("[STEP 3.5] Merging final article...")
        from .gpt_operations import merge_final_article_structured
        merge_final_article_structured(memory)
        logger.info(f"[STEP 3.5] ✅ Final article length: {len(memory['final_article'])} chars")

        if not memory["final_article"]:
            logger.error("[STEP 3.5] Final article is empty")
            return {'error': 'Fusion échouée, article final vide.'}

        # Step 4: HTML cleanup
        logger.info("[STEP 4] Cleaning HTML...")
        soup_final = BeautifulSoup(memory["final_article"], "html.parser")
        soup_final = clean_all_images(soup_final)
        soup_final = simplify_youtube_embeds(soup_final)
        soup_final = restore_youtube_iframes_from_rll_div(soup_final)
        memory["final_article"] = str(soup_final)
        logger.info(f"[STEP 4] ✅ Final cleaned HTML length: {len(memory['final_article'])} chars")

        # Step 5: Save logs
        logger.info("[STEP 5] Saving logs...")
        os.makedirs("logs/memory_pipeline", exist_ok=True)
        for k, v in memory.items():
            with open(f"logs/memory_pipeline/{k}.txt", "w", encoding="utf-8") as f:
                f.write(str(v))
        logger.info("[STEP 5] ✅ Logs saved")

        # Step 6: Save article locally
        logger.info("[STEP 6] Saving article locally...")
        output_path = "./generated/updated_pipeline_article.txt"
        os.makedirs("generated", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(memory["final_article"])
        logger.info(f"[STEP 6] ✅ Article saved to {output_path}")

        # Step 7: WordPress authentication
        logger.info("[STEP 7] Authenticating with WordPress...")
        username = os.getenv("USERNAME_WP")
        password = os.getenv("PASSWORD_WP")
        logger.info(f"[STEP 7] Username: {username}")

        jwt_token = get_jwt_token(username, password)
        if not jwt_token:
            logger.error("[STEP 7] JWT authentication failed")
            return {'error': "Échec de l'authentification WordPress"}
        logger.info("[STEP 7] ✅ JWT token obtained")

        # Step 8: Get post ID
        logger.info("[STEP 8] Getting post ID...")
        slug = extract_slug_from_url(article_url)
        logger.info(f"[STEP 8] Extracted slug: {slug}")

        post_id = get_post_id_from_slug(slug, jwt_token)
        if not post_id:
            logger.error(f"[STEP 8] Post not found for slug: {slug}")
            return {'error': f"Article introuvable pour le slug '{slug}'"}
        logger.info(f"[STEP 8] ✅ Post ID found: {post_id}")

        # Step 9: Update WordPress
        logger.info("[STEP 9] Updating WordPress...")
        success = update_wordpress_article(post_id, output_path, jwt_token)
        if not success:
            logger.error("[STEP 9] WordPress update failed")
            return {'error': "Échec de la mise à jour sur WordPress"}
        logger.info(f"[STEP 9] ✅ WordPress updated successfully")

        logger.info("=== PIPELINE COMPLETED SUCCESSFULLY ===")
        return {
            "message": f"✅ Article mis à jour avec succès sur WordPress (ID {post_id})",
            "updated_html": memory["final_article"],
            "post_id": post_id
        }

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"=== PIPELINE FAILED ===")
        logger.error(f"Error: {str(e)}")
        logger.error(f"Traceback: {error_details}")
        return {'error': f'Erreur interne : {str(e)}'}


def update_and_reconstruct_article(filepath, subject, additional_content):
    """
    Update and reconstruct article from HTML blocks
    """
    logger.info("[RECONSTRUCT] Starting article reconstruction...")

    html = load_html_file(filepath)
    logger.info(f"[RECONSTRUCT] Loaded HTML length: {len(html)} chars")

    blocks = extract_html_blocks(html)
    logger.info(f"[RECONSTRUCT] Extracted {len(blocks)} blocks")

    updated_blocks = []

    for i, block in enumerate(blocks):
        title_text = "Sans titre"
        if block['title']:
            title_text = block['title'].get_text() if hasattr(block['title'], 'get_text') else 'Sans titre'

        logger.info(f"[RECONSTRUCT] Processing block {i + 1}/{len(blocks)}: {title_text}")
        updated_block = update_block_if_needed(block, subject, additional_content)
        updated_blocks.append(updated_block)

    reconstructed = reconstruct_blocks(updated_blocks)
    logger.info(f"[RECONSTRUCT] ✅ Reconstruction complete, length: {len(reconstructed)} chars")

    return reconstructed
import os
import requests
from urllib.parse import urlparse
from langchain_core.tools import tool
from typing import Optional

from app.config import settings
from app.agents.utils.wordpress_client import WordPressClient
from app.agents.utils.html_processor import HTMLProcessor
from app.agents.utils.file_utils import FileUtils


@tool
def download_article(article_url: str) -> dict:
    """Download the original article from the given URL"""
    try:
        print(f"[TOOL] Downloading article from: {article_url}")
        response = requests.get(article_url, timeout=30)
        response.raise_for_status()

        # Save to temp file
        temp_path = FileUtils.save_temp_file(response.text, "article.html")

        return {
            "success": True,
            "content": response.text,
            "temp_path": temp_path,
            "error": None
        }
    except Exception as e:
        return {
            "success": False,
            "content": None,
            "temp_path": None,
            "error": str(e)
        }


@tool
def extract_article_slug(article_url: str) -> dict:
    """Extract the slug from the article URL"""
    try:
        path = urlparse(article_url).path
        parts = [p for p in path.strip("/").split("/") if p]
        slug = parts[-1] if parts else None

        return {
            "success": True,
            "slug": slug,
            "error": None
        }
    except Exception as e:
        return {
            "success": False,
            "slug": None,
            "error": str(e)
        }


@tool
def get_wordpress_token() -> dict:
    """Get JWT token for WordPress authentication"""
    try:
        wp_client = WordPressClient()
        token = wp_client.get_jwt_token(settings.username_wp, settings.password_wp)

        return {
            "success": True,
            "token": token,
            "error": None
        }
    except Exception as e:
        return {
            "success": False,
            "token": None,
            "error": str(e)
        }


@tool
def get_post_id_from_slug(slug: str, jwt_token: str) -> dict:
    """Get WordPress post ID from slug"""
    try:
        wp_client = WordPressClient()
        post_id = wp_client.get_post_id_from_slug(slug, jwt_token)

        return {
            "success": True,
            "post_id": post_id,
            "error": None
        }
    except Exception as e:
        return {
            "success": False,
            "post_id": None,
            "error": str(e)
        }


@tool
def extract_html_blocks(html_content: str) -> dict:
    """Extract HTML blocks from the article"""
    try:
        processor = HTMLProcessor()
        blocks = processor.extract_html_blocks(html_content)

        return {
            "success": True,
            "blocks": blocks,
            "error": None
        }
    except Exception as e:
        return {
            "success": False,
            "blocks": None,
            "error": str(e)
        }


@tool
def reconstruct_html_blocks(blocks: list) -> dict:
    """Reconstruct HTML from blocks"""
    try:
        processor = HTMLProcessor()
        html = processor.reconstruct_blocks(blocks)

        return {
            "success": True,
            "html": html,
            "error": None
        }
    except Exception as e:
        return {
            "success": False,
            "html": None,
            "error": str(e)
        }


@tool
def clean_html_content(html_content: str) -> dict:
    """Clean and optimize HTML content"""
    try:
        processor = HTMLProcessor()
        cleaned_html = processor.clean_all_content(html_content)

        return {
            "success": True,
            "html": cleaned_html,
            "error": None
        }
    except Exception as e:
        return {
            "success": False,
            "html": None,
            "error": str(e)
        }


@tool
def update_wordpress_article(post_id: int, html_content: str, jwt_token: str) -> dict:
    """Update WordPress article with new content"""
    try:
        # Save content to temp file
        temp_path = FileUtils.save_temp_file(html_content, "final_article.txt")

        wp_client = WordPressClient()
        success = wp_client.update_wordpress_article(post_id, temp_path, jwt_token)

        return {
            "success": success,
            "post_id": post_id if success else None,
            "error": None if success else "Failed to update WordPress article"
        }
    except Exception as e:
        return {
            "success": False,
            "post_id": None,
            "error": str(e)
        }
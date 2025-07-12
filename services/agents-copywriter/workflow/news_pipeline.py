from writing.news_nodes import generate_news_node
from writing.writer_nodes import optimize_article
from utils.wordpress import get_jwt_token, post_article_to_wordpress, render_report_to_markdown, markdown_to_html
from utils.prompts import load_prompt_template
import os
import json
import re


def publish_to_wordpress(article, metadata, banner_image=None):
    """
    Handle WordPress publishing with optional banner image
    """
    # Authenticate
    USERNAME = os.getenv("USERNAME_WP")
    PASSWORD = os.getenv("PASSWORD_WP")
    token = get_jwt_token(USERNAME, PASSWORD)

    if not token:
        print("[ERROR] ❌ Failed to retrieve WordPress token")
        return None

    # Parse article if needed
    if isinstance(article, str):
        try:
            clean_article = re.sub(r"^```json|```$", "", article.strip(), flags=re.MULTILINE).strip()
            parsed_article = json.loads(clean_article)
        except json.JSONDecodeError as e:
            print(f"[ERROR] Failed to parse article: {e}")
            return None
    else:
        parsed_article = article

    # Add metadata for renderer
    parsed_article['post_type'] = metadata.post_type

    # Convert to HTML
    markdown = render_report_to_markdown(parsed_article)
    html = markdown_to_html(markdown)

    # IMPORT THE NEW FUNCTION
    from utils.wordpress import post_article_to_wordpress_with_image

    # Publish with banner image - THIS IS THE KEY FIX
    post_id = post_article_to_wordpress_with_image(parsed_article, token, html, banner_image)
    return post_id


def run_news_article_pipeline(request):
    """
    Simplified pipeline for news articles - no interviews needed
    """
    metadata = request.metadata

    # Prepare state for news generation
    report_structure = load_prompt_template(metadata.post_type)

    news_state = {
        "title": f"News: {metadata.main_kw}",
        "headlines": metadata.headlines,
        "post_type": metadata.post_type,
        "report_structure": report_structure,
        "source_content": request.source_content,  # Use the property
        "audience": request.audience
    }

    # Step 1: Generate news article
    print("[DEBUG] Generating news article...")
    article_result = generate_news_node(news_state)
    article = article_result.get("article")

    if not article:
        print("[ERROR] ❌ Failed to generate news article")
        return None

    # Step 2: Optimize article
    print("[DEBUG] Optimizing article...")
    optimized_article = optimize_article(article, metadata.headlines)

    if not optimized_article:
        print("[ERROR] ❌ Failed to optimize article")
        return None

    # Step 3: WordPress publishing WITH BANNER IMAGE
    print(f"[DEBUG] Publishing to WordPress with banner: {request.banner_image}")
    return publish_to_wordpress(optimized_article, metadata, request.banner_image)
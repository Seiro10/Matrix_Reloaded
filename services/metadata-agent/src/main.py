from dotenv import load_dotenv

load_dotenv()
from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
import logging
import os
import sys
from datetime import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
import requests
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Metadata Generator Agent",
    description="Generates optimized metadata for content creation",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration for copywriter agent
COPYWRITER_AGENT_URL = os.getenv("COPYWRITER_AGENT_URL", "http://copywriter-agent:8083")


# Models
class MetadataResponse(BaseModel):
    success: bool
    article_url: str
    main_keyword: str
    secondary_keywords: List[str]
    meta_description: str
    content_type: str
    headlines: List[str]
    session_id: Optional[str] = None
    error: Optional[str] = None


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "metadata-generator-agent",
        "timestamp": datetime.now().isoformat(),
        "environment": os.getenv("ENVIRONMENT", "development")
    }


@app.post("/generate-metadata")
async def generate_metadata(payload: Dict[str, Any] = Body(...)) -> MetadataResponse:
    """
    Generate metadata based on router agent output

    Args:
        payload: The router agent output containing SERP data

    Returns:
        MetadataResponse with generated metadata
    """
    try:
        logger.info(f"Received metadata generation request")

        # Extract data from router payload
        keyword = payload.get("keyword", "")
        site_info = payload.get("site_config", {})  # Direct access to site_info

        # Extract SERP data from the payload structure
        serp_data = payload.get("serp_analysis", {})
        top_results = serp_data.get("top_results", [])
        people_also_ask = serp_data.get("people_also_ask", [])

        # Extract similar keywords
        similar_keywords_data = payload.get("similar_keywords", [])
        similar_keywords = [k.get("keyword") for k in similar_keywords_data if k.get("keyword")]

        # Get language from site info
        language = site_info.get("language", "FR")

        logger.info(f"Processing metadata for keyword: {keyword}, language: {language}")

        # Generate article URL
        slug = keyword.lower().replace(" ", "-")
        domain = site_info.get("domain", "example.com")
        article_url = f"https://{domain}/{slug}/"

        # Generate metadata using the processed data
        metadata = generate_content_metadata(
            keyword=keyword,
            similar_keywords=similar_keywords[:3] if similar_keywords else [],
            top_results=top_results,
            people_also_ask=people_also_ask,
            language=language
        )

        logger.info(f"Generated metadata for keyword: {keyword}")

        # Print notification (for future API call to copywriter)
        print(f"✅ Metadata generated for '{keyword}' in {language}")
        print(f"📊 Content type: {metadata['content_type']}")
        print(f"🔍 Meta description: {metadata['meta_description']}")
        print(f"📝 Headlines: {len(metadata['headlines'])} generated")
        print(f"📤 Sending data to copywriter for '{keyword}'")

        response_data = MetadataResponse(
            success=True,
            article_url=article_url,
            main_keyword=metadata["main_keyword"],
            secondary_keywords=metadata["secondary_keywords"],
            meta_description=metadata["meta_description"],
            content_type=metadata["content_type"],
            headlines=metadata["headlines"],
            session_id=f"metadata_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )

        logger.info(f"Metadata generation successful")
        return response_data

    except Exception as e:
        logger.error(f"Error generating metadata: {e}")
        return MetadataResponse(
            success=False,
            article_url="",
            main_keyword=keyword if 'keyword' in locals() else "",
            secondary_keywords=[],
            meta_description="",
            content_type="",
            headlines=[],
            error=str(e)
        )


def generate_content_metadata(
        keyword: str,
        similar_keywords: List[str],
        top_results: List[Dict[str, Any]],
        people_also_ask: List[str],
        language: str
) -> Dict[str, Any]:
    """
    Generate optimized metadata for content creation

    Args:
        keyword: The primary keyword
        similar_keywords: List of related keywords
        top_results: List of top competitors from SERP
        people_also_ask: List of related questions
        language: Content language (FR, EN, etc.)

    Returns:
        Dictionary with generated metadata
    """
    # Determine content type based on SERP results
    content_type = determine_content_type(top_results, keyword)

    # Extract headlines from competitors
    competitor_headlines = []
    for result in top_results:
        structure = result.get("content_structure", [])
        if structure:
            competitor_headlines.extend(structure[:5])

    # Generate optimized headlines
    optimized_headlines = generate_optimized_headlines(
        keyword,
        competitor_headlines,
        people_also_ask,
        language
    )

    # Create metadata object
    metadata = {
        "main_keyword": keyword,
        "secondary_keywords": similar_keywords[:3],
        "meta_description": generate_meta_description(keyword, top_results, language),
        "content_type": content_type,
        "headlines": optimized_headlines
    }

    return metadata


def determine_content_type(top_results: List[Dict[str, Any]], keyword: str) -> str:
    """Determine the type of content to create (Affiliate, News, Guide)"""
    # Check for affiliate indicators in titles
    affiliate_indicators = ["meilleur", "best", "top", "guide d'achat", "buying guide", "review", "test", "avis"]

    # Check for news indicators
    news_indicators = ["nouveau", "new", "sortie", "release", "annonce", "announcement", "actualité"]

    affiliate_score = 0
    news_score = 0
    guide_score = 0

    # Score based on top results
    for result in top_results:
        title = result.get("title", "").lower()

        # Check for affiliate indicators
        if any(indicator in title.lower() for indicator in affiliate_indicators):
            affiliate_score += 1

        # Check for news indicators
        if any(indicator in title.lower() for indicator in news_indicators):
            news_score += 1

        # Check for guide indicators (longer content, how-to)
        if "how" in title.lower() or "comment" in title.lower() or "guide" in title.lower():
            guide_score += 1

    # Add score based on keyword itself
    if any(indicator in keyword.lower() for indicator in affiliate_indicators):
        affiliate_score += 2

    if any(indicator in keyword.lower() for indicator in news_indicators):
        news_score += 2

    # Determine content type based on highest score
    if affiliate_score >= news_score and affiliate_score >= guide_score:
        return "Affiliate"
    elif news_score >= affiliate_score and news_score >= guide_score:
        return "News"
    else:
        return "Guide"


def generate_meta_description(keyword: str, top_results: List[Dict[str, Any]], language: str) -> str:
    """Generate optimized meta description (max 160 characters)"""
    # Extract meta descriptions from top results
    competitor_metas = []
    for result in top_results:
        meta = result.get("meta_description", "")
        if meta:
            competitor_metas.append(meta)

    # Create meta description based on language
    if language == "FR":
        prefix = f"Découvrez tout sur {keyword}: "
        suffix = ". Guide complet et conseils."
    elif language == "ES":
        prefix = f"Descubra todo sobre {keyword}: "
        suffix = ". Guía completa y consejos."
    elif language == "DE":
        prefix = f"Entdecken Sie alles über {keyword}: "
        suffix = ". Kompletter Leitfaden und Tipps."
    else:  # Default to English
        prefix = f"Discover everything about {keyword}: "
        suffix = ". Complete guide and tips."

    # Use competitor meta as inspiration if available
    if competitor_metas:
        # Take the first part of the best competitor meta
        best_meta = max(competitor_metas, key=len)
        content_part = best_meta[:80].strip()

        # Combine with our prefix
        meta = f"{prefix}{content_part}"

        # Add suffix if there's room
        if len(meta) < 130:
            meta += suffix

        # Ensure it's not too long
        if len(meta) > 160:
            meta = meta[:157] + "..."

        return meta

    # Fallback if no competitor metas
    base_meta = f"{prefix}"

    # Add additional context based on keyword
    if len(base_meta) + len(keyword) + 50 <= 160:
        if language == "FR":
            base_meta += f"informations, comparatifs et avis sur {keyword}."
        elif language == "ES":
            base_meta += f"información, comparativas y opiniones sobre {keyword}."
        elif language == "DE":
            base_meta += f"Informationen, Vergleiche und Meinungen zu {keyword}."
        else:  # Default to English
            base_meta += f"information, comparisons and reviews about {keyword}."

    # Ensure it's not too long
    if len(base_meta) > 160:
        base_meta = base_meta[:157] + "..."

    return base_meta


def generate_optimized_headlines(
        keyword: str,
        competitor_headlines: List[str],
        people_also_ask: List[str],
        language: str
) -> List[str]:
    """Generate optimized headlines based on competitors and PAA questions"""
    # Start with introduction based on language
    if language == "FR":
        headlines = [f"Introduction à {keyword}", "Ce que vous allez découvrir"]
    elif language == "ES":
        headlines = [f"Introducción a {keyword}", "Lo que vas a descubrir"]
    elif language == "DE":
        headlines = [f"Einführung in {keyword}", "Was Sie entdecken werden"]
    else:  # Default to English
        headlines = [f"Introduction to {keyword}", "What you'll discover"]

    # Add people also ask questions (up to 3)
    for question in people_also_ask[:3]:
        if question and len(question) > 10:
            headlines.append(question)

    # Add competitor headlines (avoiding duplicates)
    for headline in competitor_headlines:
        if headline and len(headline) > 5:
            # Check if similar headline already exists
            if not any(similar(headline, h) for h in headlines):
                headlines.append(headline)

                # Limit to 10 total headlines
                if len(headlines) >= 10:
                    break

    # Add conclusion based on language
    if language == "FR":
        headlines.append("Conclusion et avis final")
    elif language == "ES":
        headlines.append("Conclusión y opinión final")
    elif language == "DE":
        headlines.append("Fazit und abschließende Meinung")
    else:  # Default to English
        headlines.append("Conclusion and final thoughts")

    return headlines


def similar(a: str, b: str) -> bool:
    """Check if two headlines are similar"""
    a_lower = a.lower()
    b_lower = b.lower()

    # Direct substring
    if a_lower in b_lower or b_lower in a_lower:
        return True

    # Check if they share significant words
    a_words = set(w.lower() for w in a_lower.split() if len(w) > 3)
    b_words = set(w.lower() for w in b_lower.split() if len(w) > 3)

    # If they share more than 50% of words
    if len(a_words) > 0 and len(b_words) > 0:
        intersection = a_words.intersection(b_words)
        smaller_set = min(len(a_words), len(b_words))

        if len(intersection) / smaller_set > 0.5:
            return True

    return False


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8084))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        log_level="info"
    )
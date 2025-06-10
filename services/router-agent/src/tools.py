import sys
import os
from langchain_core.tools import tool
from typing import Dict, List, Any
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
import logging
import asyncio
import aiohttp

# Add src directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import ContentDatabase


logger = logging.getLogger(__name__)


@tool
def analyze_keyword_for_site_selection(keyword: str, similar_keywords: List[Dict]) -> Dict[str, Any]:
    """
    Analyze keyword to determine the best matching website niche

    Args:
        keyword: Main keyword to analyze
        similar_keywords: List of related keywords with metrics

    Returns:
        Dict with recommended niche, confidence score, and analysis details
    """

    # Enhanced niche detection based on French content and your 5 websites
    niche_indicators = {
        "gaming": [
            # French gaming terms
            "gaming", "gamer", "jeu", "jeux", "jeux vidéo", "fps", "mmo", "console",
            "pc gaming", "esports", "souris gamer", "clavier gaming", "clavier mécanique",
            "casque gamer", "écran gaming", "manette", "steam", "playstation", "ps5",
            "xbox", "nintendo", "battlefield", "call of duty", "league of legends",
            "valorant", "fortnite", "apex legends", "overwatch", "cs go", "csgo",
            "périphériques gaming", "setup gaming", "config gamer", "streaming"
        ],
        "motivation": [
            # French motivation and personal development terms
            "motivation", "développement personnel", "productivité", "mindset",
            "confiance en soi", "estime de soi", "objectifs", "réussite", "habitudes",
            "leadership", "coaching", "bien-être", "efficacité", "performance",
            "inspiration", "mental", "psychologie", "croissance personnelle",
            "success", "entrepreneur", "business", "formation", "développer",
            "améliorer", "changer sa vie", "positive attitude", "auto-discipline"
        ]
    }

    keyword_lower = keyword.lower()
    scores = {}

    # Score each niche
    for niche, indicators in niche_indicators.items():
        score = 0
        matched_indicators = []

        # Direct keyword matching (high weight)
        for indicator in indicators:
            if indicator in keyword_lower:
                score += 3  # High weight for direct match
                matched_indicators.append(indicator)

        # Similar keywords analysis (lower weight)
        for sim_kw in similar_keywords:
            sim_keyword_lower = sim_kw['keyword'].lower()
            for indicator in indicators:
                if indicator in sim_keyword_lower:
                    score += 1  # Lower weight for similar keywords
                    if indicator not in matched_indicators:
                        matched_indicators.append(f"{indicator} (similar)")

        scores[niche] = {
            'score': score,
            'matched_indicators': matched_indicators
        }

    # Calculate confidence and select best niche
    total_score = sum(s['score'] for s in scores.values())
    if total_score == 0:
        # Default to gaming if no clear match
        best_niche = "gaming"
        confidence = 0.3
        logger.warning(f"No niche indicators found for keyword: {keyword}, defaulting to gaming")
    else:
        best_niche = max(scores, key=lambda x: scores[x]['score'])
        confidence = scores[best_niche]['score'] / total_score

    return {
        "recommended_niche": best_niche,
        "confidence": confidence,
        "scores": {niche: data['score'] for niche, data in scores.items()},
        "analysis_details": {
            "keyword": keyword,
            "total_indicators_found": total_score,
            "winning_score": scores[best_niche]['score'],
            "matched_indicators": scores[best_niche]['matched_indicators']
        }
    }


@tool
def fetch_sitemap_content(sitemap_url: str) -> List[str]:
    """
    Fetch and parse sitemap URLs for a given website

    Args:
        sitemap_url: URL of the XML sitemap

    Returns:
        List of URLs found in the sitemap
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        logger.info(f"Fetching sitemap: {sitemap_url}")
        response = requests.get(sitemap_url, headers=headers, timeout=15)

        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'xml')
            urls = []

            # Handle different sitemap formats
            for loc in soup.find_all('loc'):
                url = loc.text.strip()
                # Filter out WordPress admin and content URLs
                if not any(exclude in url for exclude in [
                    '/wp-content/', '/wp-admin/', '/feed/', '/xmlrpc.php',
                    '/wp-json/', '/trackback/', '/comment-page-'
                ]):
                    urls.append(url)

            logger.info(f"Found {len(urls)} URLs in sitemap")
            return urls[:200]  # Limit for performance
        else:
            logger.error(f"Failed to fetch sitemap: HTTP {response.status_code}")
            return []

    except Exception as e:
        logger.error(f"Error fetching sitemap {sitemap_url}: {e}")
        return []


@tool
def check_existing_content(keyword: str, site_config: Dict, sitemap_urls: List[str]) -> Dict[str, Any]:
    """
    Check if similar content exists using both database and sitemap analysis

    Args:
        keyword: Keyword to search for
        site_config: Configuration of the selected site
        sitemap_urls: List of URLs from the sitemap

    Returns:
        Dict with content analysis results
    """

    site_id = site_config['site_id']
    db = ContentDatabase()

    logger.info(f"Checking existing content for keyword '{keyword}' on site {site_id}")

    # 1. Check database first (most accurate)
    db_result = db.search_similar_content(site_id, keyword)

    if db_result:
        logger.info(f"Found similar content in database: {db_result['title']}")
        return {
            "content_found": True,
            "source": "database",
            "content": db_result,
            "confidence": 0.9,
            "reason": f"Found in database: {db_result['similarity_reason']}"
        }

    # 2. Check sitemap URLs for keyword presence
    keyword_parts = [part.lower() for part in keyword.split() if len(part) > 2]  # Ignore short words
    matching_urls = []

    logger.info(f"Analyzing {len(sitemap_urls)} URLs from sitemap")

    for url in sitemap_urls:
        url_path = urlparse(url).path.lower()
        url_slug = url_path.split('/')[-1] if url_path.split('/')[-1] else url_path.split('/')[-2]

        # Check if keyword parts appear in URL slug/path
        matches = 0
        for part in keyword_parts:
            if part in url_slug or part in url_path:
                matches += 1

        # Calculate match score
        if matches > 0:
            match_score = matches / len(keyword_parts)
            if match_score >= 0.4:  # At least 40% of keyword parts match
                matching_urls.append({
                    "url": url,
                    "match_score": match_score,
                    "matched_parts": matches
                })

    if matching_urls:
        # Sort by match score
        matching_urls.sort(key=lambda x: x['match_score'], reverse=True)

        logger.info(f"Found {len(matching_urls)} potential URL matches")

        return {
            "content_found": True,
            "source": "sitemap",
            "content": {
                "matching_urls": matching_urls[:3],  # Top 3 matches
                "best_match": matching_urls[0]
            },
            "confidence": matching_urls[0]['match_score'],
            "reason": f"Found {len(matching_urls)} potential matches in sitemap (best: {matching_urls[0]['match_score']:.1%})"
        }

    logger.info("No similar content found")
    return {
        "content_found": False,
        "source": None,
        "content": None,
        "confidence": 0.0,
        "reason": "No similar content found in database or sitemap"
    }


@tool
def generate_internal_links(keyword: str, site_id: int, niche: str) -> List[str]:
    """
    Generate internal linking suggestions based on existing content

    Args:
        keyword: Main keyword for context
        site_id: ID of the website
        niche: Niche of the website

    Returns:
        List of internal linking suggestions
    """

    db = ContentDatabase()
    keyword_parts = [part.lower() for part in keyword.split() if len(part) > 2]
    suggestions = []

    logger.info(f"Generating internal links for keyword '{keyword}' in niche '{niche}'")

    # Search for related articles in database
    try:
        articles = db.get_articles_by_site(site_id, limit=20)

        for article in articles:
            # Check if article is related to the keyword
            article_text = f"{article['title']} {article['keywords']}".lower()

            relevance_score = 0
            for part in keyword_parts:
                if part in article_text:
                    relevance_score += 1

            if relevance_score > 0:
                suggestion = f"{article['title']} - {article['url']}"
                if suggestion not in suggestions:
                    suggestions.append(suggestion)

        logger.info(f"Found {len(suggestions)} database-based suggestions")

    except Exception as e:
        logger.error(f"Error querying database for internal links: {e}")

    # Add niche-based generic suggestions if we have few results
    if len(suggestions) < 3:
        niche_suggestions = {
            "gaming": [
                "Guide d'achat gaming - Guide complet pour choisir son matériel",
                "Tests de matériel - Nos derniers tests et reviews",
                "Actualités gaming - Les dernières news du monde du gaming"
            ],
            "motivation": [
                "Développement personnel - Guides pour améliorer sa vie",
                "Techniques de motivation - Méthodes éprouvées pour rester motivé",
                "Success stories - Histoires inspirantes de réussite"
            ]
        }

        if niche in niche_suggestions:
            suggestions.extend(niche_suggestions[niche])
            logger.info(f"Added {len(niche_suggestions[niche])} niche-based suggestions")

    return suggestions[:5]
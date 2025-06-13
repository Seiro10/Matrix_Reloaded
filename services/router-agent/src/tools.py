import sys
import os
from langchain_core.tools import tool
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import PydanticOutputParser
from typing import Dict, List, Any
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
import logging
from pydantic import BaseModel, Field

# Add src directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import ContentDatabase
from config import settings

logger = logging.getLogger(__name__)

# Initialize Claude model
llm = ChatAnthropic(
    model="claude-3-5-sonnet-20241022",
    api_key=os.getenv("ANTHROPIC_API_KEY"),
    temperature=0.1
)


# Single decision model
class IntelligentRoutingDecision(BaseModel):
    """Complete routing decision in one LLM call"""
    selected_site_niche: str = Field(description="Selected website niche: 'gaming' or 'motivation'")
    routing_decision: str = Field(description="Target agent: 'copywriter' or 'rewriter'")
    confidence: float = Field(description="Overall confidence score between 0 and 1")
    site_reasoning: str = Field(description="Why this site was selected")
    routing_reasoning: str = Field(description="Why this routing decision was made")
    content_strategy: str = Field(description="High-level content strategy recommendation")


@tool
def make_intelligent_routing_decision(
        keyword: str,
        similar_keywords: List[Dict],
        existing_content_summary: Dict[str, Any],
        serp_context: List[Dict]
) -> Dict[str, Any]:
    """
    Single intelligent LLM call to make complete routing decision

    Args:
        keyword: Main target keyword
        similar_keywords: Related keywords with metrics
        existing_content_summary: Summary of existing content analysis
        serp_context: Top SERP results for context

    Returns:
        Complete routing decision with site selection and agent target
    """

    # Prepare website information
    websites_info = """
    Available Websites:

    1. **Stuffgaming** (stuffgaming.fr) - Niche: gaming
       • Content: Gaming hardware, reviews, guides, MMORPG coverage
       • Audience: French gamers, PC/console enthusiasts
       • Keywords: gaming, jeu vidéo, hardware, périphériques, esports, streaming

    2. **Motivation Plus** (motivationplus.fr) - Niche: motivation  
       • Content: Personal development, productivity, mindset coaching
       • Audience: French professionals seeking growth
       • Keywords: motivation, développement personnel, productivité, leadership
    """

    # Prepare similar keywords summary
    similar_kw_text = "\n".join([
        f"• {kw.get('keyword', 'N/A')} ({kw.get('monthly_searches', 0)} searches)"
        for kw in similar_keywords[:5]
    ])

    # Prepare existing content summary
    content_summary = "No existing content found"
    if existing_content_summary.get('content_found'):
        source = existing_content_summary.get('source', 'unknown')
        confidence = existing_content_summary.get('confidence', 0)
        if source == 'database':
            content_data = existing_content_summary.get('content', {})
            content_summary = f"Database: Found '{content_data.get('title', 'N/A')}' (confidence: {confidence:.1%})"
        else:
            matches = existing_content_summary.get('content', {}).get('matching_urls', [])
            content_summary = f"Sitemap: Found {len(matches)} similar URLs (best match: {confidence:.1%})"

    # Prepare SERP context
    serp_summary = "No SERP data available"
    if serp_context:
        serp_summary = f"Top SERP results:\n" + "\n".join([
            f"• {result.get('title', 'N/A')}" for result in serp_context[:3]
        ])

    system_prompt = """You are an expert content strategist and SEO specialist. 

Your task is to make TWO key decisions in one analysis:
1. **Site Selection**: Which website is the best fit for this keyword
2. **Routing Decision**: Should we create new content (copywriter) or update existing (rewriter)

Consider:
• Semantic keyword alignment with site niches
• Existing content quality and relevance  
• SERP competition and opportunity
• Content strategy and SEO potential

Be decisive and strategic in your recommendations."""

    human_prompt = f"""
Analyze this keyword and make complete routing decisions:

**TARGET KEYWORD:** {keyword}

**RELATED KEYWORDS:**
{similar_kw_text}

**AVAILABLE WEBSITES:**
{websites_info}

**EXISTING CONTENT ANALYSIS:**
{content_summary}

**SERP COMPETITIVE CONTEXT:**
{serp_summary}

**DECISIONS REQUIRED:**

1. **Site Selection**: Which website niche (gaming/motivation) is the best fit?

2. **Routing Decision**: 
   - COPYWRITER: Create completely new content
   - REWRITER: Update/improve existing content

3. **Strategy**: What's your recommended content approach?

Provide clear reasoning for both decisions and overall confidence level.
"""

    try:
        parser = PydanticOutputParser(pydantic_object=IntelligentRoutingDecision)

        messages = [
            SystemMessage(content=system_prompt + f"\n\n{parser.get_format_instructions()}"),
            HumanMessage(content=human_prompt)
        ]

        logger.info(f"Making routing decision for '{keyword}'...")
        response = llm.invoke(messages)

        decision = parser.parse(response.content)

        return {
            "selected_site_niche": decision.selected_site_niche,
            "routing_decision": decision.routing_decision,
            "confidence": decision.confidence,
            "site_reasoning": decision.site_reasoning,
            "routing_reasoning": decision.routing_reasoning,
            "content_strategy": decision.content_strategy,
            "combined_reasoning": f"Site: {decision.site_reasoning}\n\nRouting: {decision.routing_reasoning}\n\nStrategy: {decision.content_strategy}"
        }

    except Exception as e:
        logger.error(f"❌ Error in intelligent routing decision: {e}")
        # Fallback to simple rules
        return _fallback_intelligent_decision(keyword, existing_content_summary)


# Keep essential utility tools (non-LLM)
@tool
def fetch_sitemap_content(sitemap_url: str) -> List[str]:
    """Fetch and parse sitemap URLs (unchanged)"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        logger.info(f"Fetching sitemap: {sitemap_url}")
        response = requests.get(sitemap_url, headers=headers, timeout=15)

        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'xml')
            urls = []

            for loc in soup.find_all('loc'):
                url = loc.text.strip()
                if not any(exclude in url for exclude in [
                    '/wp-content/', '/wp-admin/', '/feed/', '/xmlrpc.php',
                    '/wp-json/', '/trackback/', '/comment-page-'
                ]):
                    urls.append(url)

            logger.info(f"   📋 Found {len(urls)} URLs")
            return urls[:200]
        else:
            logger.warning(f"   ⚠️ Sitemap fetch failed: HTTP {response.status_code}")
            return []

    except Exception as e:
        logger.error(f"   ❌ Sitemap error: {e}")
        return []


@tool
def analyze_existing_content(keyword: str, site_id: int, sitemap_urls: List[str]) -> Dict[str, Any]:
    """
    Analyze existing content using database + sitemap analysis
    (Simplified - no LLM needed here)
    """
    db = ContentDatabase()
    logger.info(f"🔍 Analyzing existing content for '{keyword}'...")

    # 1. Check database first
    db_result = db.search_similar_content(site_id, keyword)
    if db_result:
        logger.info(f"Found in database: {db_result['title']}")
        return {
            "content_found": True,
            "source": "database",
            "content": db_result,
            "confidence": 0.9,
            "summary": f"Database match: {db_result['title']}"
        }

    # 2. Check sitemap URLs for keyword matches
    keyword_parts = [part.lower() for part in keyword.split() if len(part) > 2]
    matching_urls = []

    for url in sitemap_urls:
        url_path = urlparse(url).path.lower()
        url_slug = url_path.split('/')[-1] if url_path.split('/')[-1] else url_path.split('/')[-2]

        matches = sum(1 for part in keyword_parts if part in url_slug or part in url_path)
        if matches > 0:
            match_score = matches / len(keyword_parts)
            if match_score >= 0.4:
                matching_urls.append({
                    "url": url,
                    "match_score": match_score,
                    "matched_parts": matches
                })

    if matching_urls:
        matching_urls.sort(key=lambda x: x['match_score'], reverse=True)
        best_match = matching_urls[0]
        logger.info(f" Found {len(matching_urls)} sitemap matches (best: {best_match['match_score']:.1%})")

        return {
            "content_found": True,
            "source": "sitemap",
            "content": {"matching_urls": matching_urls[:3], "best_match": best_match},
            "confidence": best_match['match_score'],
            "summary": f"Sitemap: {len(matching_urls)} URLs (best: {best_match['match_score']:.1%})"
        }

    logger.info(f" No existing content found (Database and Sitemap)")
    return {
        "content_found": False,
        "source": None,
        "content": None,
        "confidence": 0.0,
        "summary": "No existing content found"
    }


@tool
def generate_internal_links(keyword: str, site_id: int, niche: str) -> List[str]:
    """Generate internal linking suggestions (simplified)"""
    db = ContentDatabase()
    keyword_parts = [part.lower() for part in keyword.split() if len(part) > 2]
    suggestions = []

    try:
        articles = db.get_articles_by_site(site_id, limit=20)
        for article in articles:
            article_text = f"{article['title']} {article['keywords']}".lower()
            relevance_score = sum(1 for part in keyword_parts if part in article_text)
            if relevance_score > 0:
                suggestion = f"{article['title']} - {article['url']}"
                if suggestion not in suggestions:
                    suggestions.append(suggestion)
    except Exception as e:
        logger.error(f"Database query error: {e}")

    # Add niche-based fallbacks
    if len(suggestions) < 3:
        niche_suggestions = {
            "gaming": [
                "Guide d'achat gaming - Guide complet matériel",
                "Tests hardware - Reviews et comparatifs",
                "Actualités gaming - News et tendances"
            ],
            "motivation": [
                "Développement personnel - Guides pratiques",
                "Techniques motivation - Méthodes éprouvées",
                "Success stories - Témoignages inspirants"
            ]
        }
        if niche in niche_suggestions:
            suggestions.extend(niche_suggestions[niche])

    logger.info(f"🔗 Generated {len(suggestions[:5])} internal link suggestions")
    return suggestions[:5]


def _fallback_intelligent_decision(keyword: str, existing_content: Dict[str, Any]) -> Dict[str, Any]:
    """Fallback decision logic if LLM fails"""
    keyword_lower = keyword.lower()

    # Simple niche detection
    gaming_indicators = ["gaming", "gamer", "jeu", "jeux", "console", "pc", "fps", "mmo"]
    motivation_indicators = ["motivation", "développement", "productivité", "confiance", "objectifs"]

    gaming_score = sum(1 for indicator in gaming_indicators if indicator in keyword_lower)
    motivation_score = sum(1 for indicator in motivation_indicators if indicator in keyword_lower)

    if gaming_score > motivation_score:
        selected_niche = "gaming"
    elif motivation_score > gaming_score:
        selected_niche = "motivation"
    else:
        selected_niche = "gaming"  # Default

    # Simple routing decision
    has_content = existing_content.get('content_found', False)
    confidence = existing_content.get('confidence', 0)

    if has_content and confidence > 0.5:
        routing = "rewriter"
        routing_reason = f"Found existing content with {confidence:.1%} confidence"
    else:
        routing = "copywriter"
        routing_reason = "No relevant existing content found"

    return {
        "selected_site_niche": selected_niche,
        "routing_decision": routing,
        "confidence": 0.6,
        "site_reasoning": f"Fallback: Detected {selected_niche} keywords",
        "routing_reasoning": routing_reason,
        "content_strategy": "Fallback strategy - basic keyword matching",
        "combined_reasoning": f"Fallback analysis due to LLM error. {routing_reason}"
    }
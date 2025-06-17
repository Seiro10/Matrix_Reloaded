import sys
import os
from langchain_core.tools import tool
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import PydanticOutputParser
from typing import Dict, List, Any
import requests
import logging
import json
from pydantic import BaseModel, Field

# Add src directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import ContentDatabase

logger = logging.getLogger(__name__)

# Initialize Claude model
llm = ChatAnthropic(
    model="claude-3-5-sonnet-20241022",
    api_key=os.getenv("ANTHROPIC_API_KEY"),
    temperature=0.1
)


class ContentAnalysis(BaseModel):
    """Direct content analysis from WordPress articles"""
    best_match: Dict[str, Any] = Field(description="Best matching article data")
    confidence: float = Field(description="Confidence score 0-1")
    has_similar_content: bool = Field(description="Whether similar content exists")
    reasoning: str = Field(description="Why this content matches or doesn't match")


class IntelligentRoutingDecision(BaseModel):
    """Complete routing decision in one LLM call"""
    selected_site_niche: str = Field(description="Selected website niche: 'gaming' or 'motivation'")
    routing_decision: str = Field(description="Target agent: 'copywriter' or 'rewriter'")
    confidence: float = Field(description="Overall confidence score between 0 and 1")
    combined_reasoning: str = Field(description="Complete reasoning for both decisions")


@tool
def fetch_wordpress_articles(wordpress_api_url: str) -> str:
    """Fetch all articles from WordPress API and save to JSON"""
    articles = []
    page = 1
    per_page = 100

    try:
        while True:
            response = requests.get(f"{wordpress_api_url}posts", params={
                "page": page,
                "per_page": per_page,
                "status": "publish"
            }, timeout=10)

            if response.status_code != 200:
                break

            posts = response.json()
            if not posts:
                break

            for post in posts:
                # Get excerpt content
                excerpt_content = post.get("excerpt", {}).get("rendered", "")

                # Clean HTML from excerpt
                if excerpt_content:
                    from bs4 import BeautifulSoup
                    excerpt_content = BeautifulSoup(excerpt_content, 'html.parser').get_text().strip()

                articles.append({
                    "id": post["id"],
                    "title": post["title"]["rendered"],
                    "url": post["link"],
                    "slug": post["slug"],
                    "excerpt": excerpt_content,
                    "meta_description": post.get("yoast_head_json", {}).get("og_description", ""),
                    "date": post["date"]
                })

            page += 1
            if page > 5:  # Limit to 5 pages max
                break

    except Exception as e:
        logger.error(f"Error fetching WordPress articles: {e}")

    # Save to JSON file
    site_name = wordpress_api_url.split("//")[1].split("/")[0].replace(".", "_")
    json_file = f"./data/{site_name}_articles.json"
    os.makedirs("./data", exist_ok=True)

    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)

    logger.info(f"✅ Fetched {len(articles)} articles, saved to {json_file}")
    return json_file


@tool
def analyze_wordpress_content(keyword: str, articles_file: str) -> Dict[str, Any]:
    """
    Analyze WordPress articles for content similarity using title, excerpt, slug, URL
    """
    try:
        with open(articles_file, 'r', encoding='utf-8') as f:
            articles = json.load(f)

        if not articles:
            return {
                "content_found": False,
                "best_match": None,
                "confidence": 0.0,
                "reasoning": "No articles found in WordPress API"
            }

        # Simple but effective keyword matching
        keyword_lower = keyword.lower()
        keyword_words = [word.strip() for word in keyword_lower.split() if len(word.strip()) > 2]

        best_match = None
        best_score = 0.0

        for article in articles:
            # Combine all searchable text
            searchable_text = f"{article['title']} {article['slug']} {article['excerpt']}".lower()

            # Calculate match score
            word_matches = sum(1 for word in keyword_words if word in searchable_text)
            score = word_matches / len(keyword_words) if keyword_words else 0

            # Boost score for title matches
            title_matches = sum(1 for word in keyword_words if word in article['title'].lower())
            if title_matches > 0:
                score += title_matches * 0.2

            # Boost score for slug matches (exact keyword match in URL structure)
            slug_matches = sum(1 for word in keyword_words if word in article['slug'].lower())
            if slug_matches > 0:
                score += slug_matches * 0.3

            if score > best_score:
                best_score = score
                best_match = article

        # Determine if content is similar enough for rewriting
        has_similar = best_score >= 0.4  # 40% keyword overlap threshold

        result = {
            "content_found": has_similar,
            "best_match": best_match,
            "confidence": min(best_score, 1.0),
            "reasoning": f"Best match: '{best_match['title'] if best_match else 'None'}' with {best_score:.1%} similarity"
        }

        logger.info(f"📊 Content analysis: {result['reasoning']}")
        return result

    except Exception as e:
        logger.error(f"❌ Error analyzing WordPress content: {e}")
        return {
            "content_found": False,
            "best_match": None,
            "confidence": 0.0,
            "reasoning": f"Error analyzing content: {str(e)}"
        }


@tool
def make_intelligent_routing_decision(
        keyword: str,
        gaming_content: Dict[str, Any],
        motivation_content: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Make intelligent routing decision based on WordPress content analysis
    """
    try:
        # Prepare content summaries
        gaming_summary = f"Gaming site analysis: {gaming_content.get('reasoning', 'No analysis')}"
        motivation_summary = f"Motivation site analysis: {motivation_content.get('reasoning', 'No analysis')}"

        # Determine best site based on content confidence
        gaming_confidence = gaming_content.get('confidence', 0)
        motivation_confidence = motivation_content.get('confidence', 0)

        # Site selection logic
        if gaming_confidence > motivation_confidence:
            selected_site = "gaming"
            site_confidence = gaming_confidence
            best_content = gaming_content
        elif motivation_confidence > gaming_confidence:
            selected_site = "motivation"
            site_confidence = motivation_confidence
            best_content = motivation_content
        else:
            # Fallback to keyword analysis
            keyword_lower = keyword.lower()
            gaming_indicators = ["gaming", "gamer", "jeu", "jeux", "console", "pc", "fps", "mmo", "hardware", "périphérique"]
            motivation_indicators = ["motivation", "développement", "productivité", "confiance", "objectifs", "mindset"]

            gaming_score = sum(1 for indicator in gaming_indicators if indicator in keyword_lower)
            motivation_score = sum(1 for indicator in motivation_indicators if indicator in keyword_lower)

            if gaming_score >= motivation_score:
                selected_site = "gaming"
                site_confidence = 0.5
                best_content = gaming_content
            else:
                selected_site = "motivation"
                site_confidence = 0.5
                best_content = motivation_content

        # Routing decision: rewriter if we have good content match, copywriter otherwise
        has_content = best_content.get('content_found', False)
        content_confidence = best_content.get('confidence', 0)

        if has_content and content_confidence >= 0.4:
            routing_decision = "rewriter"
            routing_reason = f"Found similar content with {content_confidence:.1%} confidence"
        else:
            routing_decision = "copywriter"
            routing_reason = "No sufficiently similar content found, creating new content"

        # Calculate overall confidence
        overall_confidence = min(site_confidence + 0.2, 1.0) if has_content else site_confidence

        reasoning = f"""
Site Selection: {selected_site} (confidence: {site_confidence:.1%})
- Gaming analysis: {gaming_summary}
- Motivation analysis: {motivation_summary}

Routing Decision: {routing_decision}
- Reason: {routing_reason}
- Best match: {best_content.get('best_match', {}).get('title', 'None') if best_content.get('best_match') else 'None'}

Overall confidence: {overall_confidence:.1%}
        """.strip()

        logger.info(f"🎯 Routing decision: {selected_site} -> {routing_decision} ({overall_confidence:.1%})")

        return {
            "selected_site_niche": selected_site,
            "routing_decision": routing_decision,
            "confidence": overall_confidence,
            "combined_reasoning": reasoning,
            "best_content_match": best_content
        }

    except Exception as e:
        logger.error(f"❌ Error in routing decision: {e}")
        return {
            "selected_site_niche": "gaming",  # Fallback
            "routing_decision": "copywriter",
            "confidence": 0.3,
            "combined_reasoning": f"Fallback decision due to error: {str(e)}",
            "best_content_match": None
        }


@tool
def generate_internal_links(keyword: str, site_id: int, niche: str) -> List[str]:
    """Generate internal linking suggestions"""
    db = ContentDatabase()
    suggestions = []

    try:
        articles = db.get_articles_by_site(site_id, limit=20)
        keyword_parts = [part.lower() for part in keyword.split() if len(part) > 2]

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
"""
Fixed Router Agent - agent.py
Simplified to send proper JSON to rewriter agent
"""

import sys
import os
from typing import Dict, Any
from datetime import datetime
from langgraph.checkpoint.memory import InMemorySaver
import requests
import logging

# Add src directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tools import (
    fetch_wordpress_articles,
    analyze_wordpress_content,
    make_intelligent_routing_decision,
    generate_internal_links
)
from config import WEBSITES
from models import RouterState, ContentFinderOutput, SiteInfo, RoutingMetadata, OutputPayload
from langgraph.graph import StateGraph, START, END

logger = logging.getLogger(__name__)

# Configuration for agent services
REWRITER_AGENT_URL = os.getenv("REWRITER_AGENT_URL", "http://localhost:8082")
COPYWRITER_AGENT_URL = os.getenv("COPYWRITER_AGENT_URL", "http://localhost:8083")
METADATA_GENERATOR_URL = os.getenv("METADATA_GENERATOR_URL", "http://localhost:8084")


<<<<<<< HEAD
def call_metadata_generator_sync(csv_file_path: str, keyword: str) -> Dict[str, Any]:
    """Synchronous call to the Metadata Generator API with CSV file"""
    try:
        logger.info(f"🔄 Calling Metadata Generator for keyword: {keyword}")

        with open(csv_file_path, 'rb') as f:
            files = {'file': (os.path.basename(csv_file_path), f, 'text/csv')}
            response = requests.post(
                f"{METADATA_GENERATOR_URL}/generate-metadata",
                files=files,
                timeout=30
            )
=======
def call_rewriter_agent_json(article_url: str, keyword: str, additional_content: str) -> Dict[str, Any]:
    """Call rewriter agent with JSON payload instead of CSV"""
    try:
        logger.info(f"🔄 Calling Rewriter Agent for keyword: {keyword}")
        logger.info(f"📄 Article URL: {article_url}")

        payload = {
            "article_url": article_url,
            "subject": keyword,
            "additional_content": additional_content
        }

        response = requests.post(
            f"{REWRITER_AGENT_URL}/update-blog-article",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=60
        )
>>>>>>> 7f2a00bfb863d843f2cea21b986c11ba7f976bd7

        if response.status_code == 200:
            result = response.json()
            logger.info(f"✅ Metadata Generator called successfully")
            return {
                "success": True,
                "message": result.get("message"),
<<<<<<< HEAD
                "metadata_response": result
            }
        else:
            logger.error(f"❌ Metadata Generator call failed: {response.status_code}")
=======
                "post_id": result.get("post_id"),
                "updated_html": result.get("updated_html", ""),
                "rewriter_response": result
            }
        else:
            logger.error(f"❌ Rewriter Agent call failed: {response.status_code}")
            logger.error(f"Response: {response.text}")
>>>>>>> 7f2a00bfb863d843f2cea21b986c11ba7f976bd7
            return {
                "success": False,
                "error": f"HTTP {response.status_code}: {response.text}",
                "metadata_response": None
            }

    except Exception as e:
        logger.error(f"❌ Error calling Metadata Generator: {e}")
        return {
            "success": False,
            "error": str(e),
            "metadata_response": None
        }


def call_copywriter_agent_json(keyword: str, keyword_data: Dict[str, Any], site_info: Dict[str, Any]) -> Dict[str, Any]:
    """Call copywriter agent with JSON payload"""
    try:
        logger.info(f"🔄 Calling Copywriter Agent for keyword: {keyword}")

        # Prepare comprehensive payload for copywriter
        payload = {
            "keyword": keyword,
            "site_info": site_info,
            "serp_data": {
                "organic_results": keyword_data.get('organic_results', []),
                "people_also_ask": keyword_data.get('people_also_ask', []),
                "competition": keyword_data.get('competition', 'UNKNOWN'),
                "monthly_searches": keyword_data.get('monthly_searches', 0)
            }
        }

        response = requests.post(
            f"{COPYWRITER_AGENT_URL}/create",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=60
        )

        if response.status_code == 200:
            result = response.json()
            logger.info(f"✅ Copywriter Agent called successfully")
            return {
                "success": True,
                "message": result.get("message"),
                "article_id": result.get("article_id"),
                "content": result.get("content", ""),
                "copywriter_response": result
            }
        else:
            logger.error(f"❌ Copywriter Agent call failed: {response.status_code}")
            return {
                "success": False,
                "error": f"HTTP {response.status_code}: {response.text}",
                "copywriter_response": None
            }

    except Exception as e:
        logger.error(f"❌ Error calling Copywriter Agent: {e}")
        return {
            "success": False,
            "error": str(e),
            "copywriter_response": None
        }


def build_additional_content(keyword_data: Dict[str, Any]) -> str:
    """Build additional content from SERP data for rewriter"""
    content_parts = []

    # Add competitor content
    organic_results = keyword_data.get('organic_results', [])
    for i, result in enumerate(organic_results[:3], 1):
        if result.get('content'):
            content_parts.append(f"Contenu concurrent {i}: {result['content']}")

    # Add people also ask
    people_also_ask = keyword_data.get('people_also_ask', [])
    if people_also_ask:
        content_parts.append(f"Questions fréquentes: {'; '.join(people_also_ask)}")

    return "\n\n".join(content_parts)


def intelligent_routing_node(state: RouterState) -> RouterState:
    """Simplified routing node using direct WordPress content analysis"""
    input_data = state["input_data"]
    keyword = input_data.get_primary_keyword()

    logger.info(f"🧠 Starting WordPress-based routing for keyword: '{keyword}'")

    try:
        # Step 1: Fetch WordPress articles for both sites
        content_analysis = {}

        for website in WEBSITES:
            logger.info(f"📊 Analyzing {website.name} ({website.niche})...")

            articles_file = fetch_wordpress_articles.invoke(website.wordpress_api_url)
            content_result = analyze_wordpress_content.invoke({
                "keyword": keyword,
                "articles_file": articles_file
            })
            content_analysis[website.niche] = content_result

            logger.info(f"{'✅' if content_result['content_found'] else '❌'} "
                        f"{website.niche}: {content_result['confidence']:.1%} confidence")

        # Step 2: Make routing decision
        routing_decision = make_intelligent_routing_decision.invoke({
            "keyword": keyword,
            "gaming_content": content_analysis.get("gaming", {}),
            "motivation_content": content_analysis.get("motivation", {})
        })

        # Step 3: Select the website
        selected_niche = routing_decision["selected_site_niche"]
        selected_site = next(
            (site for site in WEBSITES if site.niche == selected_niche),
            WEBSITES[0]
        )

        # Step 4: Generate internal links
        internal_links = generate_internal_links.invoke({
            "keyword": keyword,
            "site_id": selected_site.site_id,
            "niche": selected_site.niche
        })

        # Step 5: Get keyword data
        keyword_data = {}
        if keyword in input_data.keywords_data:
            keyword_obj = input_data.keywords_data[keyword]
            keyword_data = {
                'organic_results': [
                    {
                        'position': result.position,
                        'title': result.title,
                        'url': result.url,
                        'snippet': result.snippet,
                        'content': result.content or '',
                    }
                    for result in keyword_obj.organic_results
                ],
                'people_also_ask': keyword_obj.people_also_ask,
                'competition': keyword_obj.competition,
                'monthly_searches': keyword_obj.monthly_searches
            }

        # Step 6: Call appropriate agent
        routing_target = routing_decision["routing_decision"]
        confidence = routing_decision["confidence"]
        reasoning = routing_decision["combined_reasoning"]
        best_content = routing_decision.get("best_content_match", {})

        agent_response = None

        if routing_target == "rewriter" and best_content.get('best_match'):
            # Call rewriter with JSON
            existing_url = best_content['best_match']['url']
            additional_content = build_additional_content(keyword_data)

            print(f"\n🔄 CALLING REWRITER AGENT")
            print(f"Keyword: {keyword}")
            print(f"Site: {selected_site.name}")
            print(f"Article to rewrite: {best_content['best_match']['title']}")
            print(f"URL: {existing_url}")
            print("=" * 50)

            agent_response = call_rewriter_agent_json(existing_url, keyword, additional_content)

        else:
            # Call copywriter with JSON
            site_info = {
                "name": selected_site.name,
                "domain": selected_site.domain,
                "niche": selected_site.niche
            }

            print(f"\n✍️ CALLING COPYWRITER AGENT")
            print(f"Keyword: {keyword}")
            print(f"Site: {selected_site.name}")
            print("=" * 50)

<<<<<<< HEAD
            if csv_file:
                agent_response = call_metadata_generator_sync(csv_file, keyword)
=======
            agent_response = call_copywriter_agent_json(keyword, keyword_data, site_info)
>>>>>>> 7f2a00bfb863d843f2cea21b986c11ba7f976bd7

        # Step 7: Create output payload
        output_payload = {
            "agent_target": routing_target,
            "keyword": keyword,
            "site_config": SiteInfo(
                site_id=selected_site.site_id,
                name=selected_site.name,
                domain=selected_site.domain,
                niche=selected_site.niche,
                theme=selected_site.theme,
                language=selected_site.language,
                sitemap_url=selected_site.sitemap_url,
                wordpress_api_url=selected_site.wordpress_api_url
            ),
            "serp_analysis": input_data.get_serp_analysis(),
            "similar_keywords": input_data.get_similar_keywords(),
            "internal_linking_suggestions": internal_links,
            "routing_metadata": RoutingMetadata(
                confidence_score=confidence,
                content_source="wordpress_api",
                timestamp=datetime.now().isoformat()
            ),
            "existing_content": best_content,
            "llm_reasoning": reasoning,
            "agent_response": agent_response
        }

        return {
            **state,
            "selected_site": {
                "site_id": selected_site.site_id,
                "name": selected_site.name,
                "domain": selected_site.domain,
                "niche": selected_site.niche,
                "theme": selected_site.theme,
                "language": selected_site.language,
                "sitemap_url": selected_site.sitemap_url,
                "wordpress_api_url": selected_site.wordpress_api_url
            },
            "routing_decision": routing_target,
            "confidence_score": confidence,
            "reasoning": reasoning,
            "output_payload": output_payload,
            "internal_linking_suggestions": internal_links,
            "existing_content": best_content,
            "agent_response": agent_response
        }

    except Exception as e:
        logger.error(f"❌ Error in WordPress-based routing: {e}")
        # Fallback to first site and copywriter
        default_site = WEBSITES[0]
        return {
            **state,
            "selected_site": {
                "site_id": default_site.site_id,
                "name": default_site.name,
                "domain": default_site.domain,
                "niche": default_site.niche,
                "theme": default_site.theme,
                "language": default_site.language,
                "sitemap_url": default_site.sitemap_url,
                "wordpress_api_url": default_site.wordpress_api_url
            },
            "routing_decision": "copywriter",
            "confidence_score": 0.3,
            "reasoning": f"Fallback due to error: {str(e)}",
            "output_payload": None,
            "internal_linking_suggestions": [],
            "existing_content": None,
            "agent_response": None
        }


def create_streamlined_router_agent():
    """Create streamlined Content Router Agent"""
    logger.info("🚀 Creating WordPress-based Content Router Agent")

    workflow = StateGraph(RouterState)
    workflow.add_node("intelligent_routing", intelligent_routing_node)
    workflow.add_edge(START, "intelligent_routing")
    workflow.add_edge("intelligent_routing", END)

    checkpointer = InMemorySaver()
    compiled_workflow = workflow.compile(checkpointer=checkpointer)

    logger.info("✅ WordPress-based Content Router Agent created")
    return compiled_workflow


async def process_content_finder_output(content_data: ContentFinderOutput) -> Dict[str, Any]:
    """Process content finder output with WordPress-based routing"""
    keyword = content_data.get_primary_keyword()
    logger.info(f"🎬 Starting WordPress-based routing for keyword: '{keyword}'")

    try:
        router_agent = create_streamlined_router_agent()
        session_id = f"wp_router_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        config = {"configurable": {"thread_id": session_id}}

        initial_state = {
            "input_data": content_data,
            "selected_site": None,
            "existing_content": None,
            "routing_decision": None,
            "confidence_score": None,
            "internal_linking_suggestions": None,
            "reasoning": None,
            "output_payload": None,
            "agent_response": None
        }

        logger.info(f"🔄 Executing WordPress-based workflow (session: {session_id})")
        result = router_agent.invoke(initial_state, config=config)

        if result["routing_decision"] and result["output_payload"]:
            logger.info(f"✅ WordPress-based routing successful: {result['routing_decision'].upper()}")

            return {
                "success": True,
                "routing_decision": result["routing_decision"],
                "selected_site": SiteInfo(**result["selected_site"]),
                "confidence_score": result["confidence_score"],
                "reasoning": result["reasoning"],
                "payload": OutputPayload(**result["output_payload"]),
                "internal_linking_suggestions": result["internal_linking_suggestions"],
                "agent_response": result.get("agent_response"),
                "is_llm_powered": True,
                "is_streamlined": True
            }
        else:
            logger.error("❌ Workflow completed but missing outputs")
            return {
                "success": False,
                "error": "WordPress-based workflow failed - missing routing decision",
                "routing_decision": None,
                "payload": None,
                "agent_response": None
            }

    except Exception as e:
        logger.error(f"❌ Error in WordPress-based routing: {e}")
        return {
            "success": False,
            "error": str(e),
            "routing_decision": None,
            "payload": None,
            "agent_response": None
        }
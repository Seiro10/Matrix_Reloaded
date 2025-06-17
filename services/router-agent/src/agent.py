"""
Simplified Router Agent - agent.py
Direct WordPress content analysis for routing decisions
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


def call_rewriter_agent_sync(csv_file_path: str, keyword: str) -> Dict[str, Any]:
    """Synchronous call to the Rewriter Agent API with CSV file"""
    try:
        logger.info(f"🔄 Calling Rewriter Agent for keyword: {keyword}")

        with open(csv_file_path, 'rb') as f:
            files = {'file': (os.path.basename(csv_file_path), f, 'text/csv')}
            response = requests.post(
                f"{REWRITER_AGENT_URL}/update-blog-article",
                files=files,
                timeout=30
            )

        if response.status_code == 200:
            result = response.json()
            logger.info(f"✅ Rewriter Agent called successfully")
            return {
                "success": True,
                "session_id": result.get("session_id"),
                "message": result.get("message"),
                "rewriter_response": result
            }
        else:
            logger.error(f"❌ Rewriter Agent call failed: {response.status_code}")
            return {
                "success": False,
                "error": f"HTTP {response.status_code}: {response.text}",
                "rewriter_response": None
            }

    except Exception as e:
        logger.error(f"❌ Error calling Rewriter Agent: {e}")
        return {
            "success": False,
            "error": str(e),
            "rewriter_response": None
        }


def call_copywriter_agent_sync(csv_file_path: str, keyword: str) -> Dict[str, Any]:
    """Synchronous call to the Copywriter Agent API with CSV file"""
    try:
        logger.info(f"🔄 Calling Copywriter Agent for keyword: {keyword}")

        with open(csv_file_path, 'rb') as f:
            files = {'file': (os.path.basename(csv_file_path), f, 'text/csv')}
            response = requests.post(
                f"{COPYWRITER_AGENT_URL}/create/csv",
                files=files,
                timeout=30
            )

        if response.status_code == 200:
            result = response.json()
            logger.info(f"✅ Copywriter Agent called successfully")
            return {
                "success": True,
                "session_id": result.get("session_id"),
                "message": result.get("message"),
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


def intelligent_routing_node(state: RouterState) -> RouterState:
    """
    Simplified routing node using direct WordPress content analysis
    """
    input_data = state["input_data"]
    keyword = input_data.get_primary_keyword()
    similar_keywords = [kw.dict() for kw in input_data.get_similar_keywords()]

    logger.info(f"🧠 Starting WordPress-based routing for keyword: '{keyword}'")

    try:
        # Step 1: Fetch WordPress articles for both sites
        logger.info(f"📋 Fetching WordPress articles for all sites...")

        content_analysis = {}

        for website in WEBSITES:
            logger.info(f"   📊 Analyzing {website.name} ({website.niche})...")

            # Fetch WordPress articles
            articles_file = fetch_wordpress_articles.invoke(website.wordpress_api_url)

            # Analyze content directly using the WordPress data
            content_result = analyze_wordpress_content.invoke({
                "keyword": keyword,
                "articles_file": articles_file
            })

            content_analysis[website.niche] = content_result

            logger.info(f"      {'✅' if content_result['content_found'] else '❌'} "
                        f"{website.niche}: {content_result['confidence']:.1%} confidence")

        # Step 2: Make routing decision based on WordPress content analysis
        logger.info(f"🤖 Making routing decision based on WordPress content...")

        routing_decision = make_intelligent_routing_decision.invoke({
            "keyword": keyword,
            "gaming_content": content_analysis.get("gaming", {}),
            "motivation_content": content_analysis.get("motivation", {})
        })

        # Step 3: Select the website based on decision
        selected_niche = routing_decision["selected_site_niche"]
        selected_site = next(
            (site for site in WEBSITES if site.niche == selected_niche),
            WEBSITES[0]  # Fallback
        )

        # Step 4: Generate internal links
        internal_links = generate_internal_links.invoke({
            "keyword": keyword,
            "site_id": selected_site.site_id,
            "niche": selected_site.niche
        })

        # Step 5: Prepare final output
        routing_target = routing_decision["routing_decision"]
        confidence = routing_decision["confidence"]
        reasoning = routing_decision["combined_reasoning"]
        best_content = routing_decision.get("best_content_match", {})

        logger.info(f"✅ WordPress-based routing complete:")
        logger.info(f"   🎯 Site: {selected_site.name} ({selected_niche})")
        logger.info(f"   📝 Decision: {routing_target.upper()}")
        logger.info(f"   📊 Confidence: {confidence:.1%}")

        # Step 6: Generate CSV and call appropriate agent
        from csv_utils import (
            create_copywriter_csv,
            create_rewriter_csv,
            get_keyword_data_from_content_finder,
            validate_rewriter_csv
        )

        keyword_data = get_keyword_data_from_content_finder(input_data, keyword)
        agent_response = None
        csv_file = None

        if routing_target == "rewriter" and best_content.get('best_match'):
            # Create rewriter CSV with the found WordPress article
            existing_url = best_content['best_match']['url']

            csv_file = create_rewriter_csv(
                existing_content_url=existing_url,
                keyword=keyword,
                keyword_data=keyword_data,
                site_info={
                    "name": selected_site.name,
                    "domain": selected_site.domain,
                    "niche": selected_site.niche
                },
                confidence=confidence
            )

            print(f"\n🔄 CALLING REWRITER AGENT")
            print(f"Keyword: {keyword}")
            print(f"Site: {selected_site.name}")
            print(f"Article to rewrite: {best_content['best_match']['title']}")
            print(f"URL: {existing_url}")
            print(f"📊 CSV created: {csv_file}")
            print("=" * 50)

            if csv_file and validate_rewriter_csv(csv_file):
                agent_response = call_rewriter_agent_sync(csv_file, keyword)
            else:
                logger.error(f"❌ CSV validation failed for rewriter")
                agent_response = {
                    "success": False,
                    "error": "CSV validation failed"
                }

        else:
            # Create copywriter CSV for new content
            csv_file = create_copywriter_csv(
                keyword=keyword,
                keyword_data=keyword_data,
                site_info={
                    "name": selected_site.name,
                    "domain": selected_site.domain,
                    "niche": selected_site.niche
                },
                confidence=confidence
            )

            print(f"\n✍️ CALLING COPYWRITER AGENT")
            print(f"Keyword: {keyword}")
            print(f"Site: {selected_site.name}")
            print(f"Similar keywords: {[k['keyword'] for k in similar_keywords[:3]]}")
            print(f"📊 CSV created: {csv_file}")
            print("=" * 50)

            if csv_file:
                agent_response = call_copywriter_agent_sync(csv_file, keyword)

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
            "csv_file": csv_file,
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
            "csv_file": csv_file,
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
            "csv_file": None,
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
                "csv_file": result.get("csv_file"),
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
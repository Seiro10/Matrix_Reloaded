import sys
import os
from typing import Dict, Any
from datetime import datetime
from langgraph.checkpoint.memory import InMemorySaver

# Add src directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tools import (
    fetch_sitemap_content,
    analyze_existing_content,
    generate_internal_links,
    make_intelligent_routing_decision,
    fetch_wordpress_articles,
    analyze_content_similarity
)
from config import WEBSITES
from models import RouterState, ContentFinderOutput, SiteInfo, RoutingMetadata, OutputPayload
from langgraph.graph import StateGraph, START, END
import logging

logger = logging.getLogger(__name__)


def intelligent_routing_node(state: RouterState) -> RouterState:
    """
    Single node that makes both site selection and routing decisions using LLM
    """
    input_data = state["input_data"]
    keyword = input_data.get_primary_keyword()
    similar_keywords = [kw.dict() for kw in input_data.get_similar_keywords()]

    logger.info(f"🧠 Starting intelligent routing for keyword: '{keyword}'")

    try:
        # Step 2: Quick existing content analysis for all sites
        logger.info(f"📋 Gathering content analysis for all sites...")

        content_analysis = {}  # Initialize here
        best_content_match = None
        best_confidence = 0
        best_site_niche = None

        for website in WEBSITES:
            # Fetch WordPress articles
            articles_file = fetch_wordpress_articles.invoke(website.wordpress_api_url)

            # Analyze content similarity using LLM
            content_result = analyze_content_similarity.invoke({
                "keyword": keyword,
                "site_articles_file": articles_file
            })

            # Store result
            content_analysis[website.niche] = content_result

            # Track the best match across all sites
            if content_result.get('confidence', 0) > best_confidence:
                best_confidence = content_result.get('confidence', 0)
                best_content_match = content_result
                best_site_niche = website.niche

        logger.info(f"🏆 Best content match: {best_site_niche} site with {best_confidence:.1%} confidence")

        # Step 3: Prepare SERP context
        serp_data = input_data.get_serp_analysis()
        serp_context = [
            {
                "title": result.title,
                "url": result.url,
                "snippet": result.meta_description
            }
            for result in serp_data.top_results[:3]
        ]

        # Step 4: Make single intelligent decision based on best match
        logger.info(f"🤖 Making single intelligent routing decision...")

        # Use the best content match for decision making
        combined_content_summary = {
            "best_match": best_content_match,
            "best_site": best_site_niche,
            "all_sites_summary": f"Gaming: {content_analysis.get('gaming', {}).get('confidence', 0):.1%} | " +
                                 f"Motivation: {content_analysis.get('motivation', {}).get('confidence', 0):.1%}"
        }

        intelligent_decision = make_intelligent_routing_decision.invoke({
            "keyword": keyword,
            "similar_keywords": similar_keywords,
            "existing_content_summary": combined_content_summary,
            "serp_context": serp_context
        })

        # Step 4: Map decision to actual website
        selected_niche = intelligent_decision["selected_site_niche"]
        selected_site = next(
            (site for site in WEBSITES if site.niche == selected_niche),
            WEBSITES[0]  # Fallback
        )

        # Step 5: Generate internal links for selected site
        internal_links = generate_internal_links.invoke({
            "keyword": keyword,
            "site_id": selected_site.site_id,
            "niche": selected_site.niche
        })

        # Step 6: Prepare final output
        routing_decision = intelligent_decision["routing_decision"]
        confidence = intelligent_decision["confidence"]
        reasoning = intelligent_decision["combined_reasoning"]

        logger.info(f"✅ Intelligent routing complete:")
        logger.info(f"   🎯 Site: {selected_site.name} ({selected_niche})")
        logger.info(f"   📝 Decision: {routing_decision.upper()}")
        logger.info(f"   📊 Confidence: {confidence:.1%}")

        # Import CSV utilities and HTTP client
        from csv_utils import (
            create_copywriter_csv,
            create_rewriter_csv,
            extract_existing_content_url,
            get_keyword_data_from_content_finder
        )
        import requests

        # Get keyword data for CSV generation
        keyword_data = get_keyword_data_from_content_finder(input_data, keyword)

        # Generate CSV and print decision output
        if routing_decision == "rewriter":
            # Extract URL for existing content
            existing_url = extract_existing_content_url(content_analysis[selected_niche])

            # Create rewriter CSV
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
            print(f"Confidence: {confidence:.1%}")
            print(f"URL to rewrite: {existing_url}")
            print(f"📊 CSV created: {csv_file}")
            print("=" * 50)
        else:
            # Create copywriter CSV
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
            print(f"Confidence: {confidence:.1%}")
            print(f"Similar keywords: {[k['keyword'] for k in similar_keywords[:3]]}")
            print(f"📊 CSV created: {csv_file}")
            print("=" * 50)

        # Create output payload
        output_payload = {
            "agent_target": routing_decision,
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
                content_source=content_analysis[selected_niche].get('source'),
                timestamp=datetime.now().isoformat()
            ),
            "existing_content": content_analysis[selected_niche].get('content'),
            "llm_reasoning": reasoning,
            "csv_file": csv_file  # Add CSV file path to payload
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
            "routing_decision": routing_decision,
            "confidence_score": confidence,
            "reasoning": reasoning,
            "output_payload": output_payload,
            "internal_linking_suggestions": internal_links,
            "existing_content": content_analysis[selected_niche],
            "csv_file": csv_file  # Add CSV file path to state
        }

    except Exception as e:
        logger.error(f"❌ Error in intelligent routing: {e}")
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
            "csv_file": None
        }


def create_streamlined_router_agent():
    """
    Create streamlined Content Router Agent with single decision node
    """
    logger.info("🚀 Creating Streamlined Content Router Agent")

    # Create simple state graph with just one node
    workflow = StateGraph(RouterState)

    # Single intelligent routing node
    workflow.add_node("intelligent_routing", intelligent_routing_node)

    # Simple flow: start → decide → end
    workflow.add_edge(START, "intelligent_routing")
    workflow.add_edge("intelligent_routing", END)

    # Compile with checkpointer
    checkpointer = InMemorySaver()
    compiled_workflow = workflow.compile(checkpointer=checkpointer)

    logger.info("✅ Streamlined Content Router Agent created")
    return compiled_workflow


async def process_content_finder_output(content_data: ContentFinderOutput) -> Dict[str, Any]:
    """
    Process content finder output with streamlined intelligent routing
    """
    keyword = content_data.get_primary_keyword()
    logger.info(f"🎬 Starting streamlined routing for keyword: '{keyword}'")

    try:
        # Create streamlined router agent
        router_agent = create_streamlined_router_agent()

        # Generate session ID
        session_id = f"streamlined_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        config = {"configurable": {"thread_id": session_id}}

        # Prepare initial state
        initial_state = {
            "input_data": content_data,
            "selected_site": None,
            "existing_content": None,
            "routing_decision": None,
            "confidence_score": None,
            "internal_linking_suggestions": None,
            "reasoning": None,
            "output_payload": None
        }

        logger.info(f"🔄 Executing streamlined workflow (session: {session_id})")

        # Execute workflow
        result = router_agent.invoke(initial_state, config=config)

        # Check results
        if result["routing_decision"] and result["output_payload"]:
            logger.info(f"✅ Streamlined routing successful: {result['routing_decision'].upper()}")

            return {
                "success": True,
                "routing_decision": result["routing_decision"],
                "selected_site": SiteInfo(**result["selected_site"]),
                "confidence_score": result["confidence_score"],
                "reasoning": result["reasoning"],
                "payload": OutputPayload(**result["output_payload"]),
                "internal_linking_suggestions": result["internal_linking_suggestions"],
                "csv_file": result.get("csv_file"),  # Include CSV file path
                "is_llm_powered": True,
                "is_streamlined": True
            }
        else:
            logger.error("❌ Workflow completed but missing outputs")
            return {
                "success": False,
                "error": "Streamlined workflow failed - missing routing decision",
                "routing_decision": None,
                "payload": None
            }

    except Exception as e:
        logger.error(f"❌ Error in streamlined routing: {e}")
        return {
            "success": False,
            "error": str(e),
            "routing_decision": None,
            "payload": None
        }
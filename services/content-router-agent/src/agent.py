import sys
import os
from typing import Dict, Any

from tools import (
    analyze_keyword_for_site_selection,
    fetch_sitemap_content,
    check_existing_content,
    generate_internal_links
)
from config import WEBSITES
from datetime import datetime
from langgraph.checkpoint.memory import InMemorySaver

# Add src directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Change relative imports to absolute imports
from models import RouterState, ContentFinderOutput, SiteInfo, RoutingMetadata, OutputPayload
from config import settings

from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
import logging

logger = logging.getLogger(__name__)


def site_selection_node(state: RouterState) -> RouterState:
    """
    Select the most appropriate website based on keyword analysis

    Args:
        state: Current router state

    Returns:
        Updated state with selected site information
    """

    input_data = state["input_data"]
    keyword = input_data.keyword
    similar_keywords = [kw.dict() for kw in input_data.similar_keywords]

    logger.info(f"🔍 Analyzing keyword for site selection: '{keyword}'")

    try:
        # Analyze keyword to determine best niche
        niche_analysis = analyze_keyword_for_site_selection.invoke({
            "keyword": keyword,
            "similar_keywords": similar_keywords
        })

        # Find the matching website
        recommended_niche = niche_analysis["recommended_niche"]
        selected_site = next(
            (site for site in WEBSITES if site.niche == recommended_niche),
            WEBSITES[0]  # Default to first site if no match
        )

        logger.info(f"✅ Selected site: {selected_site.name} (niche: {selected_site.niche})")
        logger.info(f"📊 Selection confidence: {niche_analysis['confidence']:.2%}")
        logger.info(f"🏷️ Matched indicators: {niche_analysis['analysis_details']['matched_indicators']}")

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
            "confidence_score": niche_analysis["confidence"]
        }

    except Exception as e:
        logger.error(f"❌ Error in site selection: {e}")
        # Fallback to first site
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
            "confidence_score": 0.3
        }


def content_analysis_node(state: RouterState) -> RouterState:
    """
    Analyze existing content on the selected site

    Args:
        state: Current router state with selected site

    Returns:
        Updated state with content analysis results
    """

    selected_site = state["selected_site"]
    keyword = state["input_data"].keyword

    logger.info(f"🔎 Checking existing content for keyword: '{keyword}'")
    logger.info(f"🌐 Analyzing site: {selected_site['name']} ({selected_site['domain']})")

    try:
        # Fetch sitemap URLs
        logger.info(f"📄 Fetching sitemap from: {selected_site['sitemap_url']}")
        sitemap_urls = fetch_sitemap_content.invoke(selected_site["sitemap_url"])
        logger.info(f"📋 Retrieved {len(sitemap_urls)} URLs from sitemap")

        # Check for existing content
        content_check = check_existing_content.invoke({
            "keyword": keyword,
            "site_config": selected_site,
            "sitemap_urls": sitemap_urls
        })

        # Generate internal linking suggestions
        logger.info(f"🔗 Generating internal linking suggestions")
        internal_links = generate_internal_links.invoke({
            "keyword": keyword,
            "site_id": selected_site["site_id"],
            "niche": selected_site["niche"]
        })

        logger.info(f"📝 Content analysis result: {content_check['reason']}")
        logger.info(f"🔗 Generated {len(internal_links)} internal linking suggestions")

        return {
            **state,
            "existing_content": content_check,
            "internal_linking_suggestions": internal_links
        }

    except Exception as e:
        logger.error(f"❌ Error in content analysis: {e}")
        # Return safe defaults
        return {
            **state,
            "existing_content": {
                "content_found": False,
                "source": None,
                "content": None,
                "confidence": 0.0,
                "reason": f"Error during analysis: {str(e)}"
            },
            "internal_linking_suggestions": []
        }


def routing_decision_node(state: RouterState) -> RouterState:
    """
    Make the final routing decision and prepare output payload

    Args:
        state: Current router state with all analysis completed

    Returns:
        Final state with routing decision and output payload
    """

    input_data = state["input_data"]
    keyword = input_data.keyword
    selected_site = state["selected_site"]
    existing_content = state["existing_content"]

    logger.info(f"🎯 Making routing decision for keyword: '{keyword}'")

    try:
        # Determine routing decision based on content analysis
        confidence_threshold = 0.6

        if (existing_content["content_found"] and
                existing_content["confidence"] > confidence_threshold):

            decision = "rewriter"
            reasoning = (
                f"Similar content found with {existing_content['confidence']:.1%} confidence. "
                f"{existing_content['reason']} "
                f"Routing to Rewriter Agent for content update."
            )

            logger.info(f"📝 Decision: REWRITER - Content exists, will update")

            # Prepare payload for Rewriter Agent
            output_payload = {
                "agent_target": "rewriter",
                "keyword": keyword,
                "site_config": SiteInfo(**selected_site),
                "existing_content": existing_content["content"],
                "serp_analysis": input_data.serp_analysis,
                "similar_keywords": input_data.similar_keywords,
                "internal_linking_suggestions": state["internal_linking_suggestions"],
                "routing_metadata": RoutingMetadata(
                    confidence_score=state["confidence_score"],
                    content_source=existing_content["source"],
                    timestamp=datetime.now().isoformat()
                )
            }

        else:
            decision = "copywriter"
            reasoning = (
                f"No similar content found or low confidence ({existing_content['confidence']:.1%}). "
                f"{existing_content['reason']} "
                f"Routing to Copywriter Agent for new content creation."
            )

            logger.info(f"✍️ Decision: COPYWRITER - Creating new content")

            # Prepare payload for Copywriter Agent
            output_payload = {
                "agent_target": "copywriter",
                "keyword": keyword,
                "site_config": SiteInfo(**selected_site),
                "serp_analysis": input_data.serp_analysis,
                "similar_keywords": input_data.similar_keywords,
                "internal_linking_suggestions": state["internal_linking_suggestions"],
                "routing_metadata": RoutingMetadata(
                    confidence_score=state["confidence_score"],
                    timestamp=datetime.now().isoformat()
                )
            }

        logger.info(f"✅ Routing decision completed")
        logger.info(f"📋 Reasoning: {reasoning}")

        return {
            **state,
            "routing_decision": decision,
            "reasoning": reasoning,
            "output_payload": output_payload
        }

    except Exception as e:
        logger.error(f"❌ Error in routing decision: {e}")
        # Return error state
        return {
            **state,
            "routing_decision": None,
            "reasoning": f"Error making routing decision: {str(e)}",
            "output_payload": None
        }


def create_content_router_agent():
    """
    Create the Content Router Agent using LangGraph

    Returns:
        Compiled LangGraph workflow for content routing
    """

    logger.info("🚀 Creating Content Router Agent")

    # Create the state graph
    workflow = StateGraph(RouterState)

    # Add nodes with descriptive names
    workflow.add_node("site_selection", site_selection_node)
    workflow.add_node("content_analysis", content_analysis_node)
    workflow.add_node("make_routing_decision", routing_decision_node)

    # Define the execution flow
    workflow.add_edge(START, "site_selection")
    workflow.add_edge("site_selection", "content_analysis")
    workflow.add_edge("content_analysis", "make_routing_decision")
    workflow.add_edge("make_routing_decision", END)

    # Compile with checkpointer for persistence
    checkpointer = InMemorySaver()
    compiled_workflow = workflow.compile(checkpointer=checkpointer)

    logger.info("✅ Content Router Agent created successfully")
    return compiled_workflow


async def process_content_finder_output(content_data: ContentFinderOutput) -> Dict[str, Any]:
    """
    Process output from Content Finder Agent and route to appropriate agent

    Args:
        content_data: Parsed output from Content Finder Agent

    Returns:
        Dict containing routing decision and payload for next agent
    """

    logger.info(f"🎬 Starting content routing process for keyword: '{content_data.keyword}'")

    try:
        # Create router agent instance
        router_agent = create_content_router_agent()

        # Generate unique session ID
        session_id = f"router_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        config = {
            "configurable": {
                "thread_id": session_id
            }
        }

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

        logger.info(f"🔄 Executing router workflow (session: {session_id})")

        # Execute the router workflow
        result = router_agent.invoke(initial_state, config=config)

        # Check if workflow completed successfully
        if result["routing_decision"] and result["output_payload"]:
            logger.info(f"✅ Routing completed successfully")
            logger.info(f"🎯 Decision: {result['routing_decision'].upper()}")
            logger.info(f"🌐 Selected site: {result['selected_site']['name']}")

            return {
                "success": True,
                "routing_decision": result["routing_decision"],
                "selected_site": SiteInfo(**result["selected_site"]),
                "confidence_score": result["confidence_score"],
                "reasoning": result["reasoning"],
                "payload": OutputPayload(**result["output_payload"]),
                "internal_linking_suggestions": result["internal_linking_suggestions"]
            }
        else:
            logger.error("❌ Workflow completed but missing required outputs")
            return {
                "success": False,
                "error": "Workflow completed but routing decision or payload is missing",
                "routing_decision": None,
                "payload": None
            }

    except Exception as e:
        logger.error(f"❌ Error processing content finder output: {e}")
        return {
            "success": False,
            "error": str(e),
            "routing_decision": None,
            "payload": None
        }
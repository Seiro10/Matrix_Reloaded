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
METADATA_GENERATOR_URL = os.getenv("METADATA_GENERATOR_URL", "http://localhost:8084")


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
        if response.status_code == 200:
            result = response.json()
            logger.info(f"✅ Metadata Generator called successfully")
            return {
                "success": True,
                "message": result.get("message"),
                "metadata_response": result
            }
        else:
            logger.error(f"❌ Metadata Generator call failed: {response.status_code}")
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


def create_csv_for_metadata_generator(keyword: str, keyword_data: Dict[str, Any], site_info: Dict[str, Any]) -> str:
    """Create CSV file for metadata generator when routing to copywriter"""
    import csv
    import tempfile

    try:
        # Create temporary CSV file
        temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv', encoding='utf-8')
        writer = csv.writer(temp_file)

        # Write header - MUST match exactly what metadata generator expects
        header = [
            'KW', 'competition', 'Site', 'language', 'confidence', 'monthly_searches',
            'people_also_ask', 'forum',
            'position1', 'title1', 'url1', 'snippet1', 'content1', 'structure1', 'headlines1', 'metadescription1',
            'position2', 'title2', 'url2', 'snippet2', 'content2', 'structure2', 'headlines2', 'metadescription2',
            'position3', 'title3', 'url3', 'snippet3', 'content3', 'structure3', 'headlines3', 'metadescription3'
        ]
        writer.writerow(header)

        # Prepare data
        organic_results = keyword_data.get('organic_results', [])
        people_also_ask = '; '.join(keyword_data.get('people_also_ask', []))
        forum_data = '; '.join(keyword_data.get('forum', []))

        # Prepare SERP results (up to 3) - only include if URL exists
        serp_data = {}
        for i in range(1, 4):  # positions 1-3
            if i <= len(organic_results):
                result = organic_results[i - 1]
                # Only include if URL exists (as per metadata generator logic)
                if result.get('url'):
                    serp_data[f'position{i}'] = result.get('position', i)
                    serp_data[f'title{i}'] = result.get('title', '')
                    serp_data[f'url{i}'] = result.get('url', '')
                    serp_data[f'snippet{i}'] = result.get('snippet', '')
                    serp_data[f'content{i}'] = result.get('content', '')
                    serp_data[f'structure{i}'] = result.get('structure', '')
                    # Handle headlines - convert list to semicolon-separated string
                    headlines = result.get('headlines', [])
                    if isinstance(headlines, list):
                        serp_data[f'headlines{i}'] = '; '.join(headlines)
                    else:
                        serp_data[f'headlines{i}'] = str(headlines) if headlines else ''
                    serp_data[f'metadescription{i}'] = result.get('metadescription', '')
                else:
                    # Empty data for missing URLs
                    for field in ['position', 'title', 'url', 'snippet', 'content', 'structure', 'headlines',
                                  'metadescription']:
                        serp_data[f'{field}{i}'] = ''
            else:
                # Empty data for missing results
                for field in ['position', 'title', 'url', 'snippet', 'content', 'structure', 'headlines',
                              'metadescription']:
                    serp_data[f'{field}{i}'] = ''

        # Write data row - MUST match header order exactly
        row = [
            keyword,  # KW
            keyword_data.get('competition', 'UNKNOWN'),  # competition
            site_info.get('name', ''),  # Site
            'FR',  # language - default to FR as expected by metadata generator
            f"{0.80:.2f}",  # confidence - format as string with 2 decimals
            keyword_data.get('monthly_searches', 0),  # monthly_searches
            people_also_ask,  # people_also_ask
            forum_data,  # forum
            # Competitor 1
            serp_data.get('position1', ''), serp_data.get('title1', ''), serp_data.get('url1', ''),
            serp_data.get('snippet1', ''), serp_data.get('content1', ''), serp_data.get('structure1', ''),
            serp_data.get('headlines1', ''), serp_data.get('metadescription1', ''),
            # Competitor 2
            serp_data.get('position2', ''), serp_data.get('title2', ''), serp_data.get('url2', ''),
            serp_data.get('snippet2', ''), serp_data.get('content2', ''), serp_data.get('structure2', ''),
            serp_data.get('headlines2', ''), serp_data.get('metadescription2', ''),
            # Competitor 3
            serp_data.get('position3', ''), serp_data.get('title3', ''), serp_data.get('url3', ''),
            serp_data.get('snippet3', ''), serp_data.get('content3', ''), serp_data.get('structure3', ''),
            serp_data.get('headlines3', ''), serp_data.get('metadescription3', '')
        ]
        writer.writerow(row)

        temp_file.close()
        logger.info(f"✅ Created CSV for metadata generator: {temp_file.name}")
        logger.info(f"   📊 Keyword: {keyword}")
        logger.info(f"   🏢 Site: {site_info.get('name', 'Unknown')}")
        logger.info(
            f"   🔗 Competitors with URLs: {len([url for url in [serp_data.get(f'url{i}') for i in range(1, 4)] if url])}")
        return temp_file.name

    except Exception as e:
        logger.error(f"❌ Error creating CSV for metadata generator: {e}")
        return None


def call_rewriter_agent_json(existing_url: str, keyword: str, additional_content: str) -> Dict[str, Any]:
    """Call rewriter agent with JSON payload instead of CSV"""
    try:
        logger.info(f"🔄 Calling Rewriter Agent for keyword: {keyword}")

        # Prepare payload for rewriter
        payload = {
            "existing_url": existing_url,
            "keyword": keyword,
            "additional_content": additional_content
        }

        response = requests.post(
            f"{REWRITER_AGENT_URL}/rewrite",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=60
        )

        if response.status_code == 200:
            result = response.json()
            logger.info(f"✅ Rewriter Agent called successfully")
            return {
                "success": True,
                "message": result.get("message"),
                "article_id": result.get("article_id"),
                "content": result.get("content", ""),
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
            # Create CSV and call metadata generator for copywriter path
            site_info = {
                "name": selected_site.name,
                "domain": selected_site.domain,
                "niche": selected_site.niche
            }

            print(f"\n✍️ CALLING METADATA GENERATOR (COPYWRITER PATH)")
            print(f"Keyword: {keyword}")
            print(f"Site: {selected_site.name}")
            print("=" * 50)

            # Create CSV file for metadata generator
            csv_file = create_csv_for_metadata_generator(keyword, keyword_data, site_info)

            if csv_file:
                agent_response = call_metadata_generator_sync(csv_file, keyword)
            else:
                agent_response = {
                    "success": False,
                    "error": "Failed to create CSV file for metadata generator"
                }

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
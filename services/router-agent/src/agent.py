"""
Router Agent with Human-in-the-Loop - agent.py
Added human validation steps before routing decisions
"""
import sys
import os
import io
import csv
import tempfile
from typing import Dict, Any
from datetime import datetime
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import interrupt
import requests
import logging
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
import json

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
from storage import pending_validations as _pending_validations
logger = logging.getLogger(__name__)

def get_llm():
    """Get Claude LLM instance"""
    return ChatAnthropic(
        model="claude-3-5-sonnet-20241022",
        temperature=0.3,
        max_tokens=2000
    )

# Configuration for agent services
REWRITER_AGENT_URL = os.getenv("REWRITER_AGENT_URL", "http://localhost:8085")
METADATA_GENERATOR_URL = os.getenv("METADATA_GENERATOR_URL", "http://localhost:8084")


def call_metadata_generator_sync(csv_file_path: str, keyword: str) -> Dict[str, Any]:
    """Synchronous call to the Metadata Generator API with CSV file"""
    try:
        logger.info(f"🔄 Calling Metadata Generator for keyword: {keyword}")
        logger.info(f"📁 CSV file: {csv_file_path}")

        # Verify file exists before sending
        if not os.path.exists(csv_file_path):
            logger.error(f"❌ CSV file not found: {csv_file_path}")
            return {
                "success": False,
                "error": f"CSV file not found: {csv_file_path}",
                "metadata_response": None
            }

        # Check file size
        file_size = os.path.getsize(csv_file_path)
        logger.info(f"📊 CSV file size: {file_size} bytes")

        with open(csv_file_path, 'rb') as f:
            files = {'file': (os.path.basename(csv_file_path), f, 'text/csv')}

            logger.info(f"🌐 Calling: {METADATA_GENERATOR_URL}/generate-metadata")

            response = requests.post(
                f"{METADATA_GENERATOR_URL}/generate-metadata",
                files=files,
                timeout=60  # Increased timeout
            )

        logger.info(f"📡 Response status: {response.status_code}")
        logger.info(f"📝 Response headers: {dict(response.headers)}")

        if response.status_code == 200:
            try:
                result = response.json()
                logger.info(f"✅ Metadata Generator called successfully")
                logger.info(f"📋 Response keys: {list(result.keys())}")
                return {
                    "success": True,
                    "message": result.get("message", "Metadata generated successfully"),
                    "metadata_response": result
                }
            except json.JSONDecodeError as e:
                logger.error(f"❌ Invalid JSON response: {e}")
                logger.error(f"❌ Raw response: {response.text[:500]}...")
                return {
                    "success": False,
                    "error": f"Invalid JSON response: {e}",
                    "metadata_response": None
                }
        else:
            logger.error(f"❌ Metadata Generator call failed: {response.status_code}")
            logger.error(f"❌ Response text: {response.text[:500]}...")
            return {
                "success": False,
                "error": f"HTTP {response.status_code}: {response.text}",
                "metadata_response": None
            }

    except requests.exceptions.Timeout:
        logger.error(f"❌ Timeout calling Metadata Generator")
        return {
            "success": False,
            "error": "Timeout calling metadata generator service",
            "metadata_response": None
        }
    except requests.exceptions.ConnectionError:
        logger.error(f"❌ Connection error to Metadata Generator at {METADATA_GENERATOR_URL}")
        return {
            "success": False,
            "error": f"Cannot connect to metadata generator at {METADATA_GENERATOR_URL}",
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

        # FIXED: Header must match exactly what metadata generator expects
        header = [
            'KW', 'competition', 'Site', 'language', 'confidence', 'monthly_searches',
            'people_also_ask', 'forum', 'banner_image', 'post_type',
            'position1', 'title1', 'url1', 'snippet1', 'content1', 'structure1', 'headlines1', 'metadescription1',
            'position2', 'title2', 'url2', 'snippet2', 'content2', 'structure2', 'headlines2', 'metadescription2',
            'position3', 'title3', 'url3', 'snippet3', 'content3', 'structure3', 'headlines3', 'metadescription3'
        ]
        writer.writerow(header)

        # Prepare data with safe defaults
        organic_results = keyword_data.get('organic_results', [])
        people_also_ask = keyword_data.get('people_also_ask', [])
        forum_data = keyword_data.get('forum', [])

        # Convert lists to semicolon-separated strings
        people_also_ask_str = '; '.join(people_also_ask) if people_also_ask else ''
        forum_data_str = '; '.join(forum_data) if forum_data else ''

        # Prepare SERP results (up to 3) - with safe defaults
        serp_data = {}
        for i in range(1, 4):  # positions 1-3
            if i <= len(organic_results):
                result = organic_results[i - 1]

                # Safe data extraction with defaults
                serp_data[f'position{i}'] = result.get('position', i)
                serp_data[f'title{i}'] = result.get('title', '')
                serp_data[f'url{i}'] = result.get('url', '')
                serp_data[f'snippet{i}'] = result.get('snippet', '')
                serp_data[f'content{i}'] = result.get('content', '')
                serp_data[f'structure{i}'] = result.get('structure', '')

                # Handle headlines - convert list to semicolon-separated string
                headlines = result.get('headlines', [])
                if isinstance(headlines, list):
                    serp_data[f'headlines{i}'] = '; '.join(str(h) for h in headlines)
                else:
                    serp_data[f'headlines{i}'] = str(headlines) if headlines else ''

                serp_data[f'metadescription{i}'] = result.get('metadescription', '')
            else:
                # Empty data for missing results
                for field in ['position', 'title', 'url', 'snippet', 'content', 'structure', 'headlines',
                              'metadescription']:
                    serp_data[f'{field}{i}'] = ''

        # Write data row - FIXED: Must match header order exactly
        row = [
            keyword,  # KW
            keyword_data.get('competition', 'UNKNOWN'),  # competition
            site_info.get('name', ''),  # Site
            'FR',  # language - default to FR
            '0.80',  # confidence - fixed format
            keyword_data.get('monthly_searches', 0),  # monthly_searches
            people_also_ask_str,  # people_also_ask
            forum_data_str,  # forum
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

        # Verify file was created properly
        if os.path.exists(temp_file.name):
            file_size = os.path.getsize(temp_file.name)
            logger.info(f"✅ Created CSV for metadata generator: {temp_file.name}")
            logger.info(f"   📊 Keyword: {keyword}")
            logger.info(f"   🏢 Site: {site_info.get('name', 'Unknown')}")
            logger.info(f"   📁 File size: {file_size} bytes")
            logger.info(
                f"   🔗 Competitors with URLs: {len([url for url in [serp_data.get(f'url{i}') for i in range(1, 4)] if url])}")

            # Log first few lines for debugging
            with open(temp_file.name, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                logger.info(f"   📋 CSV has {len(lines)} lines")
                if len(lines) > 0:
                    logger.info(f"   📄 Header: {lines[0].strip()}")
                if len(lines) > 1:
                    logger.info(f"   📄 Data: {lines[1][:100]}...")

            return temp_file.name
        else:
            logger.error(f"❌ CSV file was not created: {temp_file.name}")
            return None

    except Exception as e:
        logger.error(f"❌ Error creating CSV for metadata generator: {e}")
        logger.error(f"❌ Exception type: {type(e)}")
        import traceback
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        return None


def call_rewriter_agent_json(existing_url: str, keyword: str, additional_content: str) -> Dict[str, Any]:
    """Call rewriter-main with JSON payload - FIXED for new FastAPI service"""
    try:
        logger.info(f"🔄 Calling Rewriter-Main for keyword: {keyword}")

        # FIXED: Prepare payload with correct field names for rewriter-main
        payload = {
            "article_url": existing_url,  # ✅ Correct field name
            "subject": keyword,  # ✅ Correct field name
            "additional_content": additional_content  # ✅ Correct field name
        }

        logger.info(f"🔗 Calling: {REWRITER_AGENT_URL}/update-blog-article")
        logger.info(f"📦 Payload: {json.dumps(payload, indent=2)}")

        # FIXED: Use correct endpoint for rewriter-main
        response = requests.post(
            f"{REWRITER_AGENT_URL}/update-blog-article",  # ✅ Correct endpoint
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=120  # Increased timeout for processing
        )

        logger.info(f"📡 Response status: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            logger.info(f"✅ Rewriter-Main called successfully")
            logger.info(f"📝 Message: {result.get('message')}")

            return {
                "success": True,
                "message": result.get("message"),
                "article_id": result.get("post_id"),  # rewriter-main returns "post_id"
                "content": result.get("updated_html", ""),  # rewriter-main returns "updated_html"
                "rewriter_response": result
            }
        else:
            logger.error(f"❌ Rewriter-Main call failed: {response.status_code}")
            logger.error(f"❌ Response text: {response.text}")
            return {
                "success": False,
                "error": f"HTTP {response.status_code}: {response.text}",
                "rewriter_response": None
            }

    except requests.exceptions.Timeout:
        logger.error(f"❌ Timeout calling Rewriter-Main")
        return {
            "success": False,
            "error": "Timeout calling rewriter-main service",
            "rewriter_response": None
        }
    except requests.exceptions.ConnectionError:
        logger.error(f"❌ Connection error to Rewriter-Main at {REWRITER_AGENT_URL}")
        return {
            "success": False,
            "error": f"Cannot connect to rewriter-main at {REWRITER_AGENT_URL}",
            "rewriter_response": None
        }
    except Exception as e:
        logger.error(f"❌ Error calling Rewriter-Main: {e}")
        return {
            "success": False,
            "error": str(e),
            "rewriter_response": None
        }


def build_additional_content(keyword_data: Dict[str, Any]) -> str:
    """Build additional content from SERP data for rewriter-main"""
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

    # Add forum data if available
    forum_data = keyword_data.get('forum', [])
    if forum_data:
        content_parts.append(f"Discussions forum: {'; '.join(forum_data)}")

    additional_content = "\n\n".join(content_parts)

    logger.info(f"📝 Built additional content ({len(additional_content)} chars)")
    logger.info(f"   💬 {len(organic_results)} competitor contents")
    logger.info(f"   ❓ {len(people_also_ask)} FAQ items")
    logger.info(f"   🗨️ {len(forum_data)} forum discussions")

    return additional_content


def intelligent_routing_node_original(state: RouterState) -> RouterState:
    """Original routing node that completes the entire workflow without HIL"""
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

        # Step 6: Call appropriate agent immediately (no HIL)
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
            # Metadata-Generator will then call Copywriter-Agent automatically
            site_info = {
                "name": selected_site.name,
                "domain": selected_site.domain,
                "niche": selected_site.niche
            }

            print(f"\n✍️ CALLING METADATA GENERATOR (COPYWRITER PATH)")
            print(f"Keyword: {keyword}")
            print(f"Site: {selected_site.name}")
            print(f"Note: Metadata-Generator will automatically call Copywriter-Agent")
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


def intelligent_routing_node(state: RouterState) -> RouterState:
    """Routing node that analyzes content and prepares for human validation"""
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

        # Step 6: Store analysis for human validation
        routing_target = routing_decision["routing_decision"]
        confidence = routing_decision["confidence"]
        reasoning = routing_decision["combined_reasoning"]
        best_content = routing_decision.get("best_content_match", {})

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
            "internal_linking_suggestions": internal_links,
            "existing_content": best_content,
            "keyword_data": keyword_data,
            "analysis_complete": True
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
            "internal_linking_suggestions": [],
            "existing_content": None,
            "keyword_data": {},
            "analysis_complete": True
        }


def human_validation_node(state: RouterState) -> RouterState:
    """Human validation node - asks for approval of routing decision"""

    # Prepare summary for human review
    keyword = state["input_data"].get_primary_keyword()
    selected_site = state["selected_site"]
    routing_decision = state["routing_decision"]
    confidence = state["confidence_score"]
    reasoning = state["reasoning"]
    existing_content = state["existing_content"]

    summary = {
        "keyword": keyword,
        "selected_site": selected_site["name"],
        "routing_decision": routing_decision,
        "confidence_score": f"{confidence:.1%}",
        "reasoning": reasoning,
        "existing_content_found": existing_content.get("content_found", False) if existing_content else False,
        "best_match_title": existing_content.get("best_match", {}).get(
            "title") if existing_content and existing_content.get("best_match") else None
    }

    logger.info(f"🤔 Requesting human validation for: {keyword}")
    logger.info(f"   📍 Site: {selected_site['name']}")
    logger.info(f"   🎯 Decision: {routing_decision}")
    logger.info(f"   📊 Confidence: {confidence:.1%}")

    # Interrupt for human validation
    human_response = interrupt({
        "type": "routing_approval",
        "summary": summary,
        "question": f"Do you approve this routing decision for '{keyword}'?",
        "options": ["yes", "no"]
    })

    return {
        **state,
        "human_approval": human_response
    }


def human_action_choice_node(state: RouterState) -> RouterState:
    """Node to ask human what action to take after approval"""

    if state.get("human_approval") != "yes":
        logger.info("❌ Human disapproved routing decision - stopping process")
        return {
            **state,
            "final_action": "stop",
            "process_stopped": True
        }

    keyword = state["input_data"].get_primary_keyword()
    existing_content = state["existing_content"]

    # Prepare options based on existing content
    options = ["copywriter", "stop"]
    if existing_content and existing_content.get("content_found"):
        options.insert(0, "rewriter")  # Put rewriter first if content exists

    # Ask human for action choice
    action_choice = interrupt({
        "type": "action_choice",
        "keyword": keyword,
        "question": "What action would you like to take?",
        "options": options,
        "existing_content": existing_content
    })

    return {
        **state,
        "final_action": action_choice
    }


def rewriter_url_input_node(state: RouterState) -> RouterState:
    """Node to ask for URL when rewriter is chosen"""

    if state.get("final_action") != "rewriter":
        return state

    keyword = state["input_data"].get_primary_keyword()
    existing_content = state["existing_content"]
    suggested_url = existing_content.get("best_match", {}).get("url") if existing_content and existing_content.get(
        "best_match") else None

    # Ask for URL input
    url_input = interrupt({
        "type": "url_input",
        "keyword": keyword,
        "question": "Please provide the URL of the article to rewrite:",
        "suggested_url": suggested_url
    })

    return {
        **state,
        "rewriter_url": url_input
    }


def execute_action_node(state: RouterState) -> RouterState:
    """Execute the chosen action"""

    final_action = state.get("final_action")

    if final_action == "stop":
        logger.info("🛑 Process stopped by human choice")
        return {
            **state,
            "process_stopped": True,
            "agent_response": {
                "success": True,
                "message": "Process stopped by user request"
            }
        }

    keyword = state["input_data"].get_primary_keyword()
    selected_site = state["selected_site"]
    keyword_data = state.get("keyword_data", {})
    internal_links = state.get("internal_linking_suggestions", [])

    agent_response = None

    if final_action == "rewriter":
        # Call rewriter with provided URL
        rewriter_url = state.get("rewriter_url")
        if not rewriter_url:
            logger.error("❌ No URL provided for rewriter")
            return {
                **state,
                "agent_response": {
                    "success": False,
                    "error": "No URL provided for rewriter"
                }
            }

        additional_content = build_additional_content(keyword_data)

        print(f"\n🔄 CALLING REWRITER AGENT")
        print(f"Keyword: {keyword}")
        print(f"Site: {selected_site['name']}")
        print(f"URL: {rewriter_url}")
        print("=" * 50)

        agent_response = call_rewriter_agent_json(rewriter_url, keyword, additional_content)

    elif final_action == "copywriter":
        # Create CSV and call metadata generator
        site_info = {
            "name": selected_site["name"],
            "domain": selected_site["domain"],
            "niche": selected_site["niche"]
        }

        print(f"\n✍️ CALLING METADATA GENERATOR (COPYWRITER PATH)")
        print(f"Keyword: {keyword}")
        print(f"Site: {selected_site['name']}")
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

    # Create output payload
    output_payload = {
        "agent_target": final_action,
        "keyword": keyword,
        "site_config": SiteInfo(**selected_site),
        "serp_analysis": state["input_data"].get_serp_analysis(),
        "similar_keywords": state["input_data"].get_similar_keywords(),
        "internal_linking_suggestions": internal_links,
        "routing_metadata": RoutingMetadata(
            confidence_score=state["confidence_score"],
            content_source="wordpress_api",
            timestamp=datetime.now().isoformat()
        ),
        "existing_content": state["existing_content"],
        "llm_reasoning": state["reasoning"],
        "agent_response": agent_response
    }

    return {
        **state,
        "output_payload": output_payload,
        "agent_response": agent_response
    }


def create_streamlined_router_agent():
    """Create streamlined Content Router Agent - ORIGINAL VERSION"""
    logger.info("🚀 Creating WordPress-based Content Router Agent")

    workflow = StateGraph(RouterState)
    workflow.add_node("intelligent_routing", intelligent_routing_node_original)
    workflow.add_edge(START, "intelligent_routing")
    workflow.add_edge("intelligent_routing", END)

    checkpointer = InMemorySaver()
    compiled_workflow = workflow.compile(checkpointer=checkpointer)

    logger.info("✅ WordPress-based Content Router Agent created")
    return compiled_workflow


def create_human_in_the_loop_router_agent():
    """Create Content Router Agent with Human-in-the-Loop validation"""
    logger.info("🚀 Creating Human-in-the-Loop Content Router Agent")

    workflow = StateGraph(RouterState)

    # Add nodes
    workflow.add_node("intelligent_routing", intelligent_routing_node)
    workflow.add_node("human_validation", human_validation_node)
    workflow.add_node("human_action_choice", human_action_choice_node)
    workflow.add_node("rewriter_url_input", rewriter_url_input_node)
    workflow.add_node("execute_action", execute_action_node)

    # Add edges
    workflow.add_edge(START, "intelligent_routing")
    workflow.add_edge("intelligent_routing", "human_validation")
    workflow.add_edge("human_validation", "human_action_choice")
    workflow.add_edge("human_action_choice", "rewriter_url_input")
    workflow.add_edge("rewriter_url_input", "execute_action")
    workflow.add_edge("execute_action", END)

    checkpointer = InMemorySaver()
    compiled_workflow = workflow.compile(checkpointer=checkpointer)

    logger.info("✅ Human-in-the-Loop Content Router Agent created")
    return compiled_workflow


def intelligent_routing_node_with_hil(state: RouterState) -> RouterState:
    """Routing node WITH human-in-the-loop validation - used by /route endpoint"""
    input_data = state["input_data"]
    keyword = input_data.get_primary_keyword()

    logger.info(f"🧠 Starting WordPress-based routing with HIL for keyword: '{keyword}'")

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

        # Step 6: HUMAN VALIDATION - Ask for approval
        routing_target = routing_decision["routing_decision"]
        confidence = routing_decision["confidence"]
        reasoning = routing_decision["combined_reasoning"]
        best_content = routing_decision.get("best_content_match", {})

        # Prepare summary for human review
        summary = {
            "keyword": keyword,
            "selected_site": selected_site.name,
            "routing_decision": routing_target,
            "confidence_score": f"{confidence:.1%}",
            "reasoning": reasoning,
            "existing_content_found": best_content.get("content_found", False) if best_content else False,
            "best_match_title": best_content.get("best_match", {}).get("title") if best_content and best_content.get(
                "best_match") else None
        }

        logger.info(f"🤔 Requesting human validation for: {keyword}")
        logger.info(f"   📍 Site: {selected_site.name}")
        logger.info(f"   🎯 Decision: {routing_target}")
        logger.info(f"   📊 Confidence: {confidence:.1%}")

        # FIRST INTERRUPT: Ask for approval
        human_approval = interrupt({
            "type": "routing_approval",
            "summary": summary,
            "question": f"Do you approve this routing decision for '{keyword}'?",
            "options": ["yes", "no"]
        })

        if human_approval != "yes":
            logger.info("❌ Human disapproved routing decision - stopping process")
            return {
                **state,
                "process_stopped": True,
                "agent_response": {
                    "success": True,
                    "message": "Process stopped by user - routing decision not approved"
                }
            }

        # SECOND INTERRUPT: Ask for action choice
        options = ["copywriter", "stop"]
        if best_content and best_content.get("content_found"):
            options.insert(0, "rewriter")  # Put rewriter first if content exists

        final_action = interrupt({
            "type": "action_choice",
            "keyword": keyword,
            "question": "What action would you like to take?",
            "options": options,
            "existing_content": best_content
        })

        if final_action == "stop":
            logger.info("🛑 Process stopped by human choice")
            return {
                **state,
                "process_stopped": True,
                "agent_response": {
                    "success": True,
                    "message": "Process stopped by user request"
                }
            }

        # THIRD INTERRUPT: If rewriter chosen, ask for URL
        rewriter_url = None
        if final_action == "rewriter":
            suggested_url = best_content.get("best_match", {}).get("url") if best_content and best_content.get(
                "best_match") else None

            rewriter_url = interrupt({
                "type": "url_input",
                "keyword": keyword,
                "question": "Please provide the URL of the article to rewrite:",
                "suggested_url": suggested_url
            })

        # Step 7: Execute the chosen action
        agent_response = None

        if final_action == "rewriter":
            if not rewriter_url:
                logger.error("❌ No URL provided for rewriter")
                agent_response = {
                    "success": False,
                    "error": "No URL provided for rewriter"
                }
            else:
                additional_content = build_additional_content(keyword_data)

                print(f"\n🔄 CALLING REWRITER AGENT")
                print(f"Keyword: {keyword}")
                print(f"Site: {selected_site.name}")
                print(f"URL: {rewriter_url}")
                print("=" * 50)

                agent_response = call_rewriter_agent_json(rewriter_url, keyword, additional_content)

        elif final_action == "copywriter":
            # Create CSV and call metadata generator
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

        # Step 8: Create output payload
        output_payload = {
            "agent_target": final_action,
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
            "routing_decision": final_action,
            "confidence_score": confidence,
            "reasoning": reasoning,
            "output_payload": output_payload,
            "internal_linking_suggestions": internal_links,
            "existing_content": best_content,
            "agent_response": agent_response,
            "human_validated": True
        }

    except Exception as e:
        logger.error(f"❌ Error in WordPress-based routing with HIL: {e}")
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
            "agent_response": None,
            "human_validated": False
        }


def create_route_agent_with_hil():
    """Create Content Router Agent with HIL for /route endpoint"""
    logger.info("🚀 Creating Content Router Agent with HIL for /route")

    workflow = StateGraph(RouterState)
    workflow.add_node("intelligent_routing", intelligent_routing_node_with_hil)
    workflow.add_edge(START, "intelligent_routing")
    workflow.add_edge("intelligent_routing", END)

    checkpointer = InMemorySaver()
    compiled_workflow = workflow.compile(checkpointer=checkpointer)

    logger.info("✅ Content Router Agent with HIL created for /route")
    return compiled_workflow


def create_csv_for_rss_content(rss_payload, banner_image=None):
    """Create CSV data for RSS content with enhanced metadata"""

    print(f"🔄 Generating enhanced metadata for RSS content...")

    # Generate enhanced metadata using Claude
    enhanced_metadata = generate_enhanced_rss_metadata(rss_payload)

    keyword = enhanced_metadata.get("keyword", rss_payload.title)
    description = enhanced_metadata.get("description", "")
    meta_description = enhanced_metadata.get("meta_description", "")
    language = enhanced_metadata.get("language", "FR")
    real_title = enhanced_metadata.get("real_title", rss_payload.title)

    print(f"✅ Enhanced metadata generated:")
    print(f"   📰 Original RSS title: {rss_payload.title}")
    print(f"   📰 Real title: {real_title}")
    print(f"   📝 Keyword: {keyword}")
    print(f"   📄 Description: {description[:100]}...")
    print(f"   🔍 Meta description: {meta_description}")
    print(f"   🌐 Language: {language}")

    # Header must match exactly what metadata generator expects
    header = [
        'KW', 'competition', 'Site', 'language', 'confidence', 'monthly_searches',
        'people_also_ask', 'forum', 'banner_image', 'post_type', 'original_post_url',  # ADD original_post_url HERE
        'position1', 'title1', 'url1', 'snippet1', 'content1', 'structure1', 'headlines1', 'metadescription1',
        'position2', 'title2', 'url2', 'snippet2', 'content2', 'structure2', 'headlines2', 'metadescription2',
        'position3', 'title3', 'url3', 'snippet3', 'content3', 'structure3', 'headlines3', 'metadescription3'
    ]

    # Create row data with enhanced metadata
    row = [
        keyword,  # KW - enhanced keyword from Claude
        'LOW',  # competition - keep as LOW as requested
        rss_payload.destination_website,  # Site
        language,  # language - detected by Claude
        '1.0',  # confidence (high for RSS)
        0,  # monthly_searches (not applicable for news)
        '',  # people_also_ask (empty for news)
        '',  # forum (empty for news)
        rss_payload.banner_image or '',  # banner_image - USE rss_payload.banner_image INSTEAD OF PARAMETER
        rss_payload.post_type,  # post_type (should be "News")
        rss_payload.original_post_url,  # original_post_url - ADD THIS LINE
        # Competitor 1 (RSS content as reference)
        '1',  # position1
        real_title,  # title1 - USE REAL TITLE HERE
        rss_payload.url,  # url1 - use source URL
        description[:150],  # snippet1 - use enhanced description
        rss_payload.content[:1000],  # content1 - first 1000 chars of content
        '',  # structure1 (empty)
        '',  # headlines1 (empty for news)
        meta_description,  # metadescription1 - enhanced meta description
        # Competitors 2 and 3 (empty for RSS)
        '', '', '', '', '', '', '', '',  # position2 through metadescription2
        '', '', '', '', '', '', '', ''  # position3 through metadescription3
    ]

    # Save to temporary file
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv', encoding='utf-8') as temp_file:
        temp_file.write(csv_content.getvalue())
        temp_filename = temp_file.name

    # Debug info
    csv_lines = csv_content.getvalue().strip().split('\n')
    file_size = len(csv_content.getvalue().encode('utf-8'))

    logger.info(f"✅ Created enhanced CSV for RSS content: {temp_filename}")
    logger.info(f"   📰 Original title: {rss_payload.title}")
    logger.info(f"   📰 Real title: {real_title}")
    logger.info(f"   📝 Enhanced Keyword: {keyword}")
    logger.info(f"   🏢 Destination: {rss_payload.destination_website}")
    logger.info(f"   📁 File size: {file_size} bytes")
    logger.info(f"   🔗 Source URL: {rss_payload.url}")
    logger.info(f"   🔗 Original Post URL: {rss_payload.original_post_url}")  # ADD DEBUG LOG
    logger.info(f"   🖼️ Banner Image: {rss_payload.banner_image}")  # ADD DEBUG LOG
    logger.info(f"   📋 CSV has {len(csv_lines)} lines")

    return temp_filename


async def process_content_finder_output_with_api_hil(content_data: ContentFinderOutput) -> Dict[str, Any]:
    """
    Process content finder output with API-based human validation (for containers)
    """
    keyword = content_data.get_primary_keyword()
    logger.info(f"🎬 Starting API-based HIL routing for keyword: '{keyword}'")

    try:
        # Step 1: Do the analysis (same as before)
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
        if keyword in content_data.keywords_data:
            keyword_obj = content_data.keywords_data[keyword]
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

        # Step 6: Prepare validation data
        routing_target = routing_decision["routing_decision"]
        confidence = routing_decision["confidence"]
        reasoning = routing_decision["combined_reasoning"]
        best_content = routing_decision.get("best_content_match", {})

        # Step 7: Create validation request instead of interrupt
        validation_id = f"validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{keyword.replace(' ', '_')}"

        validation_data = {
            "type": "routing_approval",
            "keyword": keyword,
            "selected_site": selected_site.name,
            "routing_decision": routing_target,
            "confidence_score": f"{confidence:.1%}",
            "reasoning": reasoning,
            "existing_content_found": best_content.get("content_found", False) if best_content else False,
            "best_match_title": best_content.get("best_match", {}).get("title") if best_content and best_content.get(
                "best_match") else None,
            "question": f"Do you approve this routing decision for '{keyword}'?",
            "options": ["yes", "no"]
        }

        # Store validation request
        validation_info = {
            "data": validation_data,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "keyword": keyword,
            "routing_context": {
                "selected_site": selected_site,
                "routing_target": routing_target,
                "confidence": confidence,
                "reasoning": reasoning,
                "best_content": best_content,
                "keyword_data": keyword_data,
                "internal_links": internal_links
            }
        }

        _pending_validations[validation_id] = validation_info

        logger.info(f"📝 Validation stored in agent.py: {validation_id}")

        logger.info(f"🔔 Validation required for '{keyword}' - ID: {validation_id}")
        logger.info(f"   📍 Site: {selected_site.name}")
        logger.info(f"   🎯 Decision: {routing_target}")
        logger.info(f"   📊 Confidence: {confidence:.1%}")
        logger.info(f"   🌐 Check: GET /pending-validations")
        logger.info(
            f"   ✅ Approve: POST /submit-validation {{\"validation_id\": \"{validation_id}\", \"response\": \"yes\"}}")
        logger.info(
            f"   ❌ Reject: POST /submit-validation {{\"validation_id\": \"{validation_id}\", \"response\": \"no\"}}")

        # For now, return a pending response that includes validation info
        return {
            "success": False,  # Not completed yet
            "routing_decision": None,
            "payload": None,
            "agent_response": None,
            "validation_required": True,
            "validation_id": validation_id,
            "validation_data": validation_data,
            "message": f"Human validation required. Use validation ID: {validation_id}",
            "next_steps": {
                "check_pending": "GET /pending-validations",
                "submit_approval": f"POST /submit-validation with validation_id: {validation_id}"
            }
        }

    except Exception as e:
        logger.error(f"❌ Error in API-based HIL routing: {e}")
        return {
            "success": False,
            "error": str(e),
            "routing_decision": None,
            "payload": None,
            "agent_response": None
        }


# Keep the old function for backward compatibility
async def process_content_finder_output_original(content_data: ContentFinderOutput) -> Dict[str, Any]:
    """
    UPDATED: Uses API-based HIL for container compatibility
    """
    keyword = content_data.get_primary_keyword()
    logger.info(f"🎬 Starting API HIL routing for /route endpoint, keyword: '{keyword}'")

    try:
        # Use the API-based HIL version
        result = await process_content_finder_output_with_api_hil(content_data)

        # If validation is required, return special response
        if result.get("validation_required"):
            logger.info(f"⏸️ Validation required for '{keyword}' - ID: {result['validation_id']}")
            return {
                "success": False,
                "error": "Human validation required",
                "routing_decision": None,
                "payload": None,
                "validation_required": True,
                "validation_id": result["validation_id"],
                "message": result["message"]
            }

        return result

    except Exception as e:
        logger.error(f"❌ Error in API HIL routing for /route: {e}")
        return {
            "success": False,
            "error": str(e),
            "routing_decision": None,
            "payload": None,
            "agent_response": None
        }


async def process_content_finder_output_hil(content_data: ContentFinderOutput) -> Dict[str, Any]:
    """Process content finder output with Human-in-the-Loop validation - NEW HIL VERSION"""
    """Process content finder output with Human-in-the-Loop validation"""
    keyword = content_data.get_primary_keyword()
    logger.info(f"🎬 Starting Human-in-the-Loop routing for keyword: '{keyword}'")

    try:
        router_agent = create_human_in_the_loop_router_agent()
        session_id = f"hil_router_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        config = {"configurable": {"thread_id": session_id}}

        initial_state = {
            "input_data": content_data,
            "selected_site": None,
            "existing_content": None,
            "routing_decision": None,
            "confidence_score": None,
            "internal_linking_suggestions": None,
            "reasoning": None,
            "keyword_data": None,
            "analysis_complete": False,
            "human_approval": None,
            "final_action": None,
            "rewriter_url": None,
            "output_payload": None,
            "agent_response": None,
            "process_stopped": False
        }

        logger.info(f"🔄 Executing Human-in-the-Loop workflow (session: {session_id})")

        # The workflow will be interrupted multiple times for human input
        # The client will need to resume with human responses
        result = router_agent.invoke(initial_state, config=config)

        if result.get("process_stopped"):
            logger.info("🛑 Process stopped by human choice")
            return {
                "success": True,
                "routing_decision": "stopped",
                "selected_site": None,
                "confidence_score": 0,
                "reasoning": "Process stopped by user",
                "payload": None,
                "agent_response": result.get("agent_response"),
                "is_llm_powered": True,
                "is_human_validated": True
            }

        if result.get("output_payload") and result.get("agent_response"):
            logger.info(f"✅ Human-validated routing successful: {result.get('final_action', 'unknown').upper()}")

            return {
                "success": True,
                "routing_decision": result.get("final_action"),
                "selected_site": SiteInfo(**result["selected_site"]) if result.get("selected_site") else None,
                "confidence_score": result.get("confidence_score"),
                "reasoning": result.get("reasoning"),
                "payload": OutputPayload(**result["output_payload"]),
                "internal_linking_suggestions": result.get("internal_linking_suggestions"),
                "agent_response": result.get("agent_response"),
                "is_llm_powered": True,
                "is_human_validated": True
            }
        else:
            logger.error("❌ Workflow completed but missing outputs")
            return {
                "success": False,
                "error": "Human-validated workflow failed - missing outputs",
                "routing_decision": None,
                "payload": None,
                "agent_response": None
            }

    except Exception as e:
        logger.error(f"❌ Error in Human-in-the-Loop routing: {e}")
        return {
            "success": False,
            "error": str(e),
            "routing_decision": None,
            "payload": None,
            "agent_response": None
        }


def generate_enhanced_rss_metadata(rss_payload) -> dict:
    """
    Use Claude to generate better metadata for RSS content
    """
    try:
        llm = get_llm()

        system_prompt = """You are a content analyst that extracts and generates metadata from news articles.

Your task is to analyze RSS content and generate optimal metadata fields.

IMPORTANT: The title provided might be generic (like "MISES À JOUR DU JEU"). Look at the CONTENT to find the real, specific news title.

Generate the following fields:
1. keyword: A clear, SEO-friendly keyword that represents the main topic
2. description: A concise 2-3 sentence description of what this news article is about
3. meta_description: A compelling 150-160 character meta description for SEO
4. language: Auto-detect language (FR, EN, ES, etc.)
5. real_title: Extract the REAL news title from the content (not the generic RSS title)
6. description: 1-3 comprehensives headlines, reflecting the most important informations of the post.

Respond with ONLY a valid JSON object containing these fields."""

        human_prompt = f"""Analyze this news content and extract the REAL title:

RSS Title (might be generic): {rss_payload.title}
Content: {rss_payload.content[:2000]}  
Website: {rss_payload.website}
Theme: {rss_payload.theme}
URL: {rss_payload.url}

IMPORTANT: Look in the content for the actual news title, not just use the RSS title which might be generic.

Generate the metadata JSON based on this content."""

        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_prompt)
        ])

        # Parse the JSON response
        content = response.content.strip()

        # Try to extract JSON
        try:
            metadata = json.loads(content)
        except json.JSONDecodeError:
            # Fallback if JSON parsing fails
            start_idx = content.find('{')
            end_idx = content.rfind('}') + 1
            if start_idx != -1 and end_idx > start_idx:
                json_str = content[start_idx:end_idx]
                metadata = json.loads(json_str)
            else:
                raise ValueError("Could not extract valid JSON")

        # Use the real title if Claude found one, otherwise use original
        real_title = metadata.get("real_title", rss_payload.title)

        print(f"🤖 Generated metadata:")
        print(f"   📰 Original title: {rss_payload.title}")
        print(f"   📰 Real title: {real_title}")
        print(f"   📝 Keyword: {metadata.get('keyword', '')}")
        print(f"   🌐 Language: {metadata.get('language', 'FR')}")

        return {
            **metadata,
            "real_title": real_title
        }

    except Exception as e:
        print(f"❌ Error generating enhanced metadata: {e}")
        # Fallback to basic metadata
        return {
            "keyword": rss_payload.title,
            "description": rss_payload.content[:200] + "..." if len(rss_payload.content) > 200 else rss_payload.content,
            "meta_description": f"Découvrez les dernières actualités: {rss_payload.title}"[:160],
            "language": "FR",
            "real_title": rss_payload.title
        }
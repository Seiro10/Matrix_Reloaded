from dotenv import load_dotenv

load_dotenv()
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
import logging
import os
import sys
from datetime import datetime
from typing import Optional, Dict, Any, List 

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models import ContentFinderOutput, RouterResponse, SiteInfo, OutputPayload, RoutingMetadata, SERPAnalysis, SimilarKeyword

from agent import (
    create_human_in_the_loop_router_agent,
    build_additional_content,
    call_rewriter_agent_json,
    create_csv_for_metadata_generator,
    call_metadata_generator_sync
) 
from storage import pending_validations, active_workflows

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Content Router Agent with Human-in-the-Loop",
    description="LangGraph-based content routing microservice with human validation",
    version="2.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class StartWorkflowRequest(BaseModel):
    content_data: ContentFinderOutput


class ResumeWorkflowRequest(BaseModel):
    session_id: str
    human_response: str  # "yes"/"no" for approval, "rewriter"/"copywriter"/"stop" for action choice, or URL for rewriter


class WorkflowStatus(BaseModel):
    session_id: str
    status: str  # "waiting_approval", "waiting_action", "waiting_url", "completed", "stopped", "error"
    current_step: str
    data: Optional[Dict[str, Any]] = None


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "content-router-agent-hil",
        "timestamp": datetime.now().isoformat(),
        "environment": os.getenv("ENVIRONMENT", "development"),
        "features": ["human-in-the-loop", "workflow-resume"]
    }


@app.post("/start-workflow")
async def start_workflow(request: StartWorkflowRequest):
    """
    Start a new human-in-the-loop routing workflow

    Returns session_id and first interrupt for human validation
    """
    try:
        keyword = request.content_data.get_primary_keyword()
        logger.info(f"🚀 Starting HIL workflow for keyword: {keyword}")

        # Create workflow
        router_agent = create_human_in_the_loop_router_agent()
        session_id = f"hil_router_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        config = {"configurable": {"thread_id": session_id}}

        initial_state = {
            "input_data": request.content_data,
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

        # Store workflow info
        active_workflows[session_id] = {
            "agent": router_agent,
            "config": config,
            "status": "running",
            "created_at": datetime.now().isoformat(),
            "keyword": keyword
        }

        logger.info(f"🔄 Starting workflow execution (session: {session_id})")

        # Start workflow - it will interrupt for human validation
        try:
            for chunk in router_agent.stream(initial_state, config=config):
                # Check if we hit an interrupt
                if "__interrupt__" in chunk:
                    interrupt_data = chunk["__interrupt__"][0]

                    # Store current state
                    active_workflows[session_id]["status"] = "waiting_human_input"
                    active_workflows[session_id]["interrupt_data"] = interrupt_data.value
                    active_workflows[session_id]["interrupt_type"] = interrupt_data.value.get("type")

                    logger.info(f"⏸️ Workflow interrupted for human input: {interrupt_data.value.get('type')}")

                    return {
                        "session_id": session_id,
                        "status": "waiting_human_input",
                        "interrupt_type": interrupt_data.value.get("type"),
                        "data": interrupt_data.value,
                        "message": "Workflow paused for human input"
                    }

            # If we get here, workflow completed without interrupts (shouldn't happen)
            logger.warning(f"⚠️ Workflow completed without interrupts: {session_id}")
            active_workflows[session_id]["status"] = "completed"

            return {
                "session_id": session_id,
                "status": "completed",
                "message": "Workflow completed without human input"
            }

        except Exception as e:
            logger.error(f"❌ Error starting workflow: {e}")
            active_workflows[session_id]["status"] = "error"
            active_workflows[session_id]["error"] = str(e)
            raise HTTPException(status_code=500, detail=f"Workflow execution error: {str(e)}")

    except Exception as e:
        logger.error(f"❌ Start workflow error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/resume-workflow")
async def resume_workflow(request: ResumeWorkflowRequest):
    """
    Resume a workflow with human response
    """
    try:
        session_id = request.session_id
        human_response = request.human_response

        if session_id not in active_workflows:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

        workflow_info = active_workflows[session_id]

        if workflow_info["status"] != "waiting_human_input":
            raise HTTPException(status_code=400, detail=f"Session {session_id} is not waiting for input")

        router_agent = workflow_info["agent"]
        config = workflow_info["config"]

        logger.info(f"▶️ Resuming workflow {session_id} with response: {human_response}")

        # Resume workflow with human response
        from langgraph.types import Command

        try:
            for chunk in router_agent.stream(Command(resume=human_response), config=config):
                # Check if we hit another interrupt
                if "__interrupt__" in chunk:
                    interrupt_data = chunk["__interrupt__"][0]

                    # Update workflow state
                    workflow_info["interrupt_data"] = interrupt_data.value
                    workflow_info["interrupt_type"] = interrupt_data.value.get("type")

                    logger.info(f"⏸️ Workflow interrupted again for: {interrupt_data.value.get('type')}")

                    return {
                        "session_id": session_id,
                        "status": "waiting_human_input",
                        "interrupt_type": interrupt_data.value.get("type"),
                        "data": interrupt_data.value,
                        "message": "Workflow paused for additional human input"
                    }

                # Check if workflow completed
                if "execute_action" in chunk:
                    final_state = chunk["execute_action"]

                    # Mark workflow as completed
                    workflow_info["status"] = "completed"
                    workflow_info["final_state"] = final_state

                    logger.info(f"✅ Workflow {session_id} completed successfully")

                    # Prepare response similar to original API
                    if final_state.get("process_stopped"):
                        return {
                            "session_id": session_id,
                            "status": "completed",
                            "result": {
                                "success": True,
                                "routing_decision": "stopped",
                                "message": "Process stopped by user request",
                                "is_human_validated": True
                            }
                        }
                    else:
                        from models import SiteInfo, OutputPayload

                        return {
                            "session_id": session_id,
                            "status": "completed",
                            "result": {
                                "success": True,
                                "routing_decision": final_state.get("final_action"),
                                "selected_site": SiteInfo(**final_state["selected_site"]) if final_state.get(
                                    "selected_site") else None,
                                "confidence_score": final_state.get("confidence_score"),
                                "reasoning": final_state.get("reasoning"),
                                "payload": OutputPayload(**final_state["output_payload"]) if final_state.get(
                                    "output_payload") else None,
                                "internal_linking_suggestions": final_state.get("internal_linking_suggestions"),
                                "agent_response": final_state.get("agent_response"),
                                "is_llm_powered": True,
                                "is_human_validated": True
                            }
                        }

            # If we get here without completing, something went wrong
            logger.warning(f"⚠️ Workflow resumed but didn't complete properly: {session_id}")
            workflow_info["status"] = "error"
            workflow_info["error"] = "Workflow resumed but didn't complete"

            return {
                "session_id": session_id,
                "status": "error",
                "message": "Workflow resumed but didn't complete properly"
            }

        except Exception as e:
            logger.error(f"❌ Error resuming workflow: {e}")
            workflow_info["status"] = "error"
            workflow_info["error"] = str(e)
            raise HTTPException(status_code=500, detail=f"Resume workflow error: {str(e)}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Resume workflow error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/workflow-status/{session_id}")
async def get_workflow_status(session_id: str):
    """
    Get the current status of a workflow
    """
    if session_id not in active_workflows:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    workflow_info = active_workflows[session_id]

    return {
        "session_id": session_id,
        "status": workflow_info["status"],
        "created_at": workflow_info["created_at"],
        "keyword": workflow_info.get("keyword"),
        "interrupt_type": workflow_info.get("interrupt_type"),
        "interrupt_data": workflow_info.get("interrupt_data"),
        "error": workflow_info.get("error")
    }


@app.get("/active-workflows")
async def list_active_workflows():
    """
    List all active workflows
    """
    return {
        "workflows": [
            {
                "session_id": session_id,
                "status": info["status"],
                "created_at": info["created_at"],
                "keyword": info.get("keyword")
            }
            for session_id, info in active_workflows.items()
        ]
    }


@app.delete("/workflow/{session_id}")
async def cancel_workflow(session_id: str):
    """
    Cancel and clean up a workflow
    """
    if session_id not in active_workflows:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    del active_workflows[session_id]
    logger.info(f"🗑️ Workflow {session_id} cancelled and cleaned up")

    return {
        "message": f"Workflow {session_id} cancelled successfully"
    }


class ValidationRequest(BaseModel):
    validation_id: str
    response: str  # "yes"/"no" for approval, "rewriter"/"copywriter"/"stop" for action, or URL


@app.post("/route", response_model=RouterResponse)
async def route_content(content_data: ContentFinderOutput):
    """
    Route endpoint with API-based Human-in-the-Loop for Docker/container environments
    Creates validation requests that can be handled via the dashboard or API calls
    """
    try:
        keyword = content_data.get_primary_keyword()
        logger.info(f"🚀 Processing routing request with API-based HIL for keyword: {keyword}")

        # Use the API-based HIL that creates validation requests
        from agent import process_content_finder_output_with_api_hil
        result = await process_content_finder_output_with_api_hil(content_data)

        if result.get("validation_required"):
            # Validation is pending - return info for dashboard/API interaction
            validation_id = result["validation_id"]
            logger.info(f"⏸️ Validation required for '{keyword}' - ID: {validation_id}")
            logger.info("🎛️ Use the HIL dashboard or API endpoints to respond")

            return RouterResponse(
                success=False,  # Not completed yet
                routing_decision=None,
                selected_site=None,
                confidence_score=None,
                reasoning="Human validation required",
                payload=None,
                error=f"Human validation required. Validation ID: {validation_id}",
                is_llm_powered=True,
                is_human_validated=False
            )
        elif result.get("success"):
            # Workflow completed successfully
            logger.info(f"✅ Routing successful: {result['routing_decision']}")
            return RouterResponse(**result)
        else:
            # Workflow failed
            logger.error(f"❌ Routing failed: {result.get('error', 'Unknown error')}")
            raise HTTPException(status_code=500, detail=result.get("error", "Unknown routing error"))

    except Exception as e:
        logger.error(f"❌ Route endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/pending-validations")
async def get_pending_validations():
    """Get list of pending validations"""
    return {
        "pending_validations": [
            {
                "validation_id": vid,
                "data": data["data"],
                "created_at": data["created_at"]
            }
            for vid, data in pending_validations.items()
        ]
    }


@app.post("/submit-validation")
async def submit_validation(request: ValidationRequest):
    """Submit human validation response"""
    validation_id = request.validation_id

    if validation_id not in pending_validations:
        raise HTTPException(status_code=404, detail=f"Validation {validation_id} not found")

    # Store response and mark as completed
    pending_validations[validation_id]["response"] = request.response
    pending_validations[validation_id]["status"] = "completed"
    pending_validations[validation_id]["completed_at"] = datetime.now().isoformat()

    logger.info(f"✅ Validation {validation_id} completed with response: {request.response}")

    return {
        "message": f"Validation {validation_id} completed successfully",
        "response": request.response
    }


@app.post("/continue-workflow/{validation_id}")
async def continue_workflow(validation_id: str):
    """Continue workflow after validation is completed"""
    if validation_id not in pending_validations:
        raise HTTPException(status_code=404, detail=f"Validation {validation_id} not found")

    validation_info = pending_validations[validation_id]

    if validation_info["status"] != "completed":
        raise HTTPException(status_code=400, detail=f"Validation {validation_id} not completed yet")

    human_response = validation_info["response"]
    routing_context = validation_info["routing_context"]
    keyword = validation_info["keyword"]

    try:
        logger.info(f"▶️ Continuing workflow for {keyword} with response: {human_response}")

        # Handle routing approval response
        if validation_info["data"]["type"] == "routing_approval":
            if human_response == "yes":
                # Human approved! Check if we have a good URL to use automatically
                best_content = routing_context["best_content"]

                if best_content and best_content.get("content_found") and best_content.get("best_match", {}).get("url"):
                    # ✅ We have a suggested URL - execute rewriter directly!
                    suggested_url = best_content["best_match"]["url"]
                    logger.info(f"✅ Human approved - executing rewriter automatically with: {suggested_url}")

                    # Execute rewriter directly (existing logic)
                    selected_site = routing_context["selected_site"]
                    confidence = routing_context["confidence"]
                    reasoning = routing_context["reasoning"]
                    keyword_data = routing_context["keyword_data"]
                    internal_links = routing_context["internal_links"]

                    from agent import build_additional_content, call_rewriter_agent_json
                    additional_content = build_additional_content(keyword_data)

                    print(f"\n🔄 AUTO-CALLING REWRITER AGENT")
                    print(f"Keyword: {keyword}")
                    print(f"Site: {selected_site.name}")
                    print(f"URL: {suggested_url}")
                    print("=" * 50)

                    agent_response = call_rewriter_agent_json(suggested_url, keyword, additional_content)

                    # Create final response
                    from models import SiteInfo, OutputPayload, RoutingMetadata

                    output_payload = {
                        "agent_target": "rewriter",
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
                        "serp_analysis": routing_context.get("serp_analysis"),
                        "similar_keywords": routing_context.get("similar_keywords", []),
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

                    # Clean up validation
                    del pending_validations[validation_id]

                    logger.info(f"✅ Auto-execution completed successfully: REWRITER")

                    return {
                        "success": True,
                        "routing_decision": "rewriter",
                        "selected_site": SiteInfo(**selected_site.__dict__),
                        "confidence_score": confidence,
                        "reasoning": reasoning,
                        "payload": OutputPayload(**output_payload),
                        "internal_linking_suggestions": internal_links,
                        "agent_response": agent_response,
                        "is_llm_powered": True,
                        "is_human_validated": True,
                        "auto_executed": True
                    }

                else:
                    # No good URL found, ask for action choice
                    logger.info("⚠️ No suitable URL found, asking for action choice")

                    choice_validation_id = f"choice_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{keyword.replace(' ', '_')}"

                    choice_validation_data = {
                        "type": "action_choice",
                        "keyword": keyword,
                        "question": "What action would you like to take?",
                        "options": ["rewriter", "copywriter", "stop"]
                    }

                    pending_validations[choice_validation_id] = {
                        "data": choice_validation_data,
                        "status": "pending",
                        "created_at": datetime.now().isoformat(),
                        "keyword": keyword,
                        "routing_context": routing_context,
                        "parent_validation": validation_id
                    }

                    # Clean up original validation
                    del pending_validations[validation_id]

                    logger.info(f"🎯 Action choice required for '{keyword}' - ID: {choice_validation_id}")

                    return {
                        "success": False,
                        "validation_required": True,
                        "validation_id": choice_validation_id,
                        "validation_data": choice_validation_data,
                        "message": f"Action choice required. Use validation ID: {choice_validation_id}",
                        "step": "action_choice"
                    }

            else:  # human_response == "no"
                # NEW: Human disagreed with routing, offer 3 choices
                logger.info("❌ Human disagreed with routing decision - offering alternative choices")

                choice_validation_id = f"choice_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{keyword.replace(' ', '_')}"

                choice_validation_data = {
                    "type": "action_choice",
                    "keyword": keyword,
                    "question": "You disagreed with the routing decision. What would you like to do instead?",
                    "options": ["rewriter", "copywriter", "stop"]
                }

                pending_validations[choice_validation_id] = {
                    "data": choice_validation_data,
                    "status": "pending",
                    "created_at": datetime.now().isoformat(),
                    "keyword": keyword,
                    "routing_context": routing_context,
                    "parent_validation": validation_id
                }

                # Clean up original validation
                del pending_validations[validation_id]

                logger.info(f"🎯 Alternative action choice for '{keyword}' - ID: {choice_validation_id}")

                return {
                    "success": False,
                    "validation_required": True,
                    "validation_id": choice_validation_id,
                    "validation_data": choice_validation_data,
                    "message": f"Alternative action choice required. Use validation ID: {choice_validation_id}",
                    "step": "action_choice"
                }

        # Handle action choice response
        elif validation_info["data"]["type"] == "action_choice":
            action_choice = human_response

            if action_choice == "stop":
                # Clean up validation
                del pending_validations[validation_id]

                return {
                    "success": True,
                    "routing_decision": "stopped",
                    "message": "Process stopped by user request",
                    "is_human_validated": True
                }

            elif action_choice == "copywriter":
                # Execute copywriter path
                selected_site = routing_context["selected_site"]
                confidence = routing_context["confidence"]
                reasoning = routing_context["reasoning"]
                keyword_data = routing_context["keyword_data"]
                internal_links = routing_context["internal_links"]

                from agent import create_csv_for_metadata_generator, call_metadata_generator_sync

                site_info = {
                    "name": selected_site.name,
                    "domain": selected_site.domain,
                    "niche": selected_site.niche
                }

                print(f"\n✍️ CALLING METADATA GENERATOR (COPYWRITER PATH)")
                print(f"Keyword: {keyword}")
                print(f"Site: {selected_site.name}")
                print("=" * 50)

                csv_file = create_csv_for_metadata_generator(keyword, keyword_data, site_info)

                if csv_file:
                    agent_response = call_metadata_generator_sync(csv_file, keyword)
                else:
                    agent_response = {
                        "success": False,
                        "error": "Failed to create CSV file for metadata generator"
                    }

                # Create final response
                from models import SiteInfo, OutputPayload, RoutingMetadata

                output_payload = {
                    "agent_target": "copywriter",
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
                    "serp_analysis": routing_context.get("serp_analysis"),
                    "similar_keywords": routing_context.get("similar_keywords", []),
                    "internal_linking_suggestions": internal_links,
                    "routing_metadata": RoutingMetadata(
                        confidence_score=confidence,
                        content_source="wordpress_api",
                        timestamp=datetime.now().isoformat()
                    ),
                    "existing_content": routing_context["best_content"],
                    "llm_reasoning": reasoning,
                    "agent_response": agent_response
                }

                # Clean up validation
                del pending_validations[validation_id]

                logger.info(f"✅ Copywriter executed successfully")

                return {
                    "success": True,
                    "routing_decision": "copywriter",
                    "selected_site": SiteInfo(**selected_site.__dict__),
                    "confidence_score": confidence,
                    "reasoning": reasoning,
                    "payload": OutputPayload(**output_payload),
                    "internal_linking_suggestions": internal_links,
                    "agent_response": agent_response,
                    "is_llm_powered": True,
                    "is_human_validated": True
                }

            elif action_choice == "rewriter":
                # Ask for URL input
                logger.info("🔗 Rewriter chosen, asking for URL input")

                url_validation_id = f"url_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{keyword.replace(' ', '_')}"

                url_validation_data = {
                    "type": "url_input",
                    "keyword": keyword,
                    "question": "Please provide the full URL of the article to rewrite:",
                    "input_type": "url"
                }

                pending_validations[url_validation_id] = {
                    "data": url_validation_data,
                    "status": "pending",
                    "created_at": datetime.now().isoformat(),
                    "keyword": keyword,
                    "routing_context": routing_context,
                    "parent_validation": validation_id,
                    "action_choice": "rewriter"
                }

                # Clean up current validation
                del pending_validations[validation_id]

                logger.info(f"🔗 URL input required for '{keyword}' - ID: {url_validation_id}")

                return {
                    "success": False,
                    "validation_required": True,
                    "validation_id": url_validation_id,
                    "validation_data": url_validation_data,
                    "message": f"URL input required. Use validation ID: {url_validation_id}",
                    "step": "url_input"
                }

        elif validation_info["data"]["type"] == "url_input":
            rewriter_url = human_response

            # Execute rewriter with provided URL
            selected_site = routing_context["selected_site"]
            confidence = routing_context["confidence"]
            reasoning = routing_context["reasoning"]
            keyword_data = routing_context["keyword_data"]
            internal_links = routing_context["internal_links"]

            from agent import build_additional_content, call_rewriter_agent_json
            additional_content = build_additional_content(keyword_data)

            print(f"\n🔄 CALLING REWRITER AGENT WITH USER-PROVIDED URL")
            print(f"Keyword: {keyword}")
            print(f"Site: {selected_site.name}")
            print(f"URL: {rewriter_url}")
            print("=" * 50)

            agent_response = call_rewriter_agent_json(rewriter_url, keyword, additional_content)

            # Create final response with proper defaults for missing data
            from models import SiteInfo, OutputPayload, RoutingMetadata, SERPAnalysis, SimilarKeyword

            # Create proper SERP analysis from routing context or defaults
            serp_analysis = routing_context.get("serp_analysis")
            if not serp_analysis:
                # Create empty SERP analysis as fallback
                serp_analysis = SERPAnalysis(
                    top_results=[],
                    people_also_ask=[]
                )

            # Create proper similar keywords from routing context or defaults
            similar_keywords = routing_context.get("similar_keywords", [])
            if not similar_keywords:
                similar_keywords = []

            output_payload = {
                "agent_target": "rewriter",
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
                "serp_analysis": serp_analysis,  # Now properly created
                "similar_keywords": similar_keywords,  # Now properly created
                "internal_linking_suggestions": internal_links,
                "routing_metadata": RoutingMetadata(
                    confidence_score=confidence,
                    content_source="wordpress_api",
                    timestamp=datetime.now().isoformat()
                ),
                "existing_content": routing_context.get("best_content"),
                "llm_reasoning": reasoning,
                "agent_response": agent_response
            }

            # Clean up validation
            del pending_validations[validation_id]

            logger.info(f"✅ Rewriter executed successfully with user-provided URL")

            return {
                "success": True,
                "routing_decision": "rewriter",
                "selected_site": SiteInfo(
                    site_id=selected_site.site_id,
                    name=selected_site.name,
                    domain=selected_site.domain,
                    niche=selected_site.niche,
                    theme=selected_site.theme,
                    language=selected_site.language,
                    sitemap_url=selected_site.sitemap_url,
                    wordpress_api_url=selected_site.wordpress_api_url
                ),
                "confidence_score": confidence,
                "reasoning": reasoning,
                "payload": OutputPayload(**output_payload),
                "internal_linking_suggestions": internal_links,
                "agent_response": agent_response,
                "is_llm_powered": True,
                "is_human_validated": True
            }

    except Exception as e:
        logger.error(f"❌ Error continuing workflow: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    return 1


@app.post("/execute-action/{validation_id}")
async def execute_action(validation_id: str):
    """Execute the final action after all validations"""
    if validation_id not in pending_validations:
        raise HTTPException(status_code=404, detail=f"Validation {validation_id} not found")

    validation_info = pending_validations[validation_id]

    if validation_info["status"] != "completed":
        raise HTTPException(status_code=400, detail=f"Validation {validation_id} not completed yet")

    action_choice = validation_info["response"]
    routing_context = validation_info["routing_context"]
    keyword = validation_info["keyword"]

    try:
        logger.info(f"🎬 Executing action '{action_choice}' for keyword: {keyword}")

        if action_choice == "stop":
            # Clean up validation
            del pending_validations[validation_id]

            return {
                "success": True,
                "routing_decision": "stopped",
                "message": "Process stopped by user request",
                "is_human_validated": True
            }

        # Get context data
        selected_site = routing_context["selected_site"]
        confidence = routing_context["confidence"]
        reasoning = routing_context["reasoning"]
        best_content = routing_context["best_content"]
        keyword_data = routing_context["keyword_data"]
        internal_links = routing_context["internal_links"]

        agent_response = None

        if action_choice == "rewriter":
            # For containers, we'll use the best match URL automatically
            # (in a real UI, you'd ask for URL input)
            if best_content and best_content.get("best_match"):
                rewriter_url = best_content["best_match"]["url"]

                from agent import build_additional_content, call_rewriter_agent_json
                additional_content = build_additional_content(keyword_data)

                print(f"\n🔄 CALLING REWRITER AGENT")
                print(f"Keyword: {keyword}")
                print(f"Site: {selected_site.name}")
                print(f"URL: {rewriter_url}")
                print("=" * 50)

                agent_response = call_rewriter_agent_json(rewriter_url, keyword, additional_content)
            else:
                agent_response = {
                    "success": False,
                    "error": "No URL available for rewriter"
                }

        elif action_choice == "copywriter":
            # Execute copywriter path
            selected_site = routing_context["selected_site"]
            confidence = routing_context["confidence"]
            reasoning = routing_context["reasoning"]
            keyword_data = routing_context["keyword_data"]
            internal_links = routing_context["internal_links"]

            from agent import create_csv_for_metadata_generator, call_metadata_generator_sync

            site_info = {
                "name": selected_site.name,
                "domain": selected_site.domain,
                "niche": selected_site.niche
            }

            print(f"\n✍️ CALLING METADATA GENERATOR (COPYWRITER PATH)")
            print(f"Keyword: {keyword}")
            print(f"Site: {selected_site.name}")
            print("=" * 50)

            csv_file = create_csv_for_metadata_generator(keyword, keyword_data, site_info)

            if csv_file:
                agent_response = call_metadata_generator_sync(csv_file, keyword)
            else:
                agent_response = {
                    "success": False,
                    "error": "Failed to create CSV file for metadata generator"
                }

            # Create final response with proper defaults
            from models import SiteInfo, OutputPayload, RoutingMetadata, SERPAnalysis, SimilarKeyword

            # Create proper SERP analysis from routing context or defaults
            serp_analysis = routing_context.get("serp_analysis")
            if not serp_analysis:
                serp_analysis = SERPAnalysis(
                    top_results=[],
                    people_also_ask=[]
                )

            # Create proper similar keywords from routing context or defaults
            similar_keywords = routing_context.get("similar_keywords", [])
            if not similar_keywords:
                similar_keywords = []

            output_payload = {
                "agent_target": "copywriter",
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
                "serp_analysis": serp_analysis,  # Now properly created
                "similar_keywords": similar_keywords,  # Now properly created
                "internal_linking_suggestions": internal_links,
                "routing_metadata": RoutingMetadata(
                    confidence_score=confidence,
                    content_source="wordpress_api",
                    timestamp=datetime.now().isoformat()
                ),
                "existing_content": routing_context.get("best_content"),
                "llm_reasoning": reasoning,
                "agent_response": agent_response
            }

            # Clean up validation
            del pending_validations[validation_id]

            logger.info(f"✅ Copywriter executed successfully")

            return {
                "success": True,
                "routing_decision": "copywriter",
                "selected_site": SiteInfo(
                    site_id=selected_site.site_id,
                    name=selected_site.name,
                    domain=selected_site.domain,
                    niche=selected_site.niche,
                    theme=selected_site.theme,
                    language=selected_site.language,
                    sitemap_url=selected_site.sitemap_url,
                    wordpress_api_url=selected_site.wordpress_api_url
                ),
                "confidence_score": confidence,
                "reasoning": reasoning,
                "payload": OutputPayload(**output_payload),
                "internal_linking_suggestions": internal_links,
                "agent_response": agent_response,
                "is_llm_powered": True,
                "is_human_validated": True
            }

    except Exception as e:
        logger.error(f"❌ Error executing action: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    return 1


@app.get("/sites")
async def get_available_sites():
    """Get list of available websites for routing"""
    from config import WEBSITES

    return {
        "sites": [
            {
                "site_id": site.site_id,
                "name": site.name,
                "domain": site.domain,
                "niche": site.niche,
                "theme": site.theme,
                "language": site.language
            }
            for site in WEBSITES
        ]
    }


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        log_level="info"
    )
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
from typing import Optional, Dict, Any

# Add src directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# Change relative imports to absolute imports
from models import ContentFinderOutput, RouterResponse
from agent import create_human_in_the_loop_router_agent

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

# Store active workflows in memory (in production, use a proper database)
active_workflows: Dict[str, Any] = {}


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


# Global storage for pending validations
pending_validations: Dict[str, Any] = {}


def store_validation(validation_id: str, validation_data: Dict[str, Any]):
    """Store a validation in the global pending_validations"""
    global pending_validations
    pending_validations[validation_id] = validation_data
    logger.info(f"📝 Stored validation: {validation_id}")


# Make this function available to agent.py
import agent

agent.store_validation_func = store_validation


class ValidationRequest(BaseModel):
    validation_id: str
    response: str  # "yes"/"no" for approval, "rewriter"/"copywriter"/"stop" for action, or URL


@app.post("/route", response_model=RouterResponse)
async def route_content(content_data: ContentFinderOutput):
    """
    Route endpoint with human validation via API calls instead of terminal interrupts
    """
    try:
        keyword = content_data.get_primary_keyword()
        logger.info(f"Processing routing request with HIL for keyword: {keyword}")

        # Use the HIL workflow but handle interrupts via API
        from agent import process_content_finder_output_with_api_hil
        result = await process_content_finder_output_with_api_hil(content_data)

        if result["success"]:
            logger.info(f"Routing successful: {result['routing_decision']}")
            return RouterResponse(**result)
        else:
            logger.error(f"Routing failed: {result['error']}")
            raise HTTPException(status_code=500, detail=result["error"])

    except Exception as e:
        logger.error(f"Route endpoint error: {e}")
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

        if human_response != "yes":
            logger.info("❌ Human disapproved routing decision - stopping process")

            # Clean up validation
            del pending_validations[validation_id]

            return {
                "success": True,
                "routing_decision": "stopped",
                "message": "Process stopped - routing decision not approved",
                "is_human_validated": True
            }

        # Human approved, now ask for action choice
        best_content = routing_context["best_content"]
        options = ["copywriter", "stop"]
        if best_content and best_content.get("content_found"):
            options.insert(0, "rewriter")

        # Create action choice validation
        action_validation_id = f"action_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{keyword.replace(' ', '_')}"

        action_validation_data = {
            "type": "action_choice",
            "keyword": keyword,
            "question": "What action would you like to take?",
            "options": options,
            "existing_content": best_content
        }

        pending_validations[action_validation_id] = {
            "data": action_validation_data,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "keyword": keyword,
            "routing_context": routing_context,
            "parent_validation": validation_id
        }

        # Clean up original validation
        del pending_validations[validation_id]

        logger.info(f"🎯 Action choice required for '{keyword}' - ID: {action_validation_id}")
        logger.info(f"   Options: {', '.join(options)}")

        return {
            "success": False,  # Still pending
            "validation_required": True,
            "validation_id": action_validation_id,
            "validation_data": action_validation_data,
            "message": f"Action choice required. Use validation ID: {action_validation_id}",
            "step": "action_choice"
        }

    except Exception as e:
        logger.error(f"❌ Error continuing workflow: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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

            # Create CSV file for metadata generator
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
            "agent_target": action_choice,
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

        logger.info(f"✅ Action executed successfully: {action_choice.upper()}")

        return {
            "success": True,
            "routing_decision": action_choice,
            "selected_site": SiteInfo(**selected_site.__dict__),
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
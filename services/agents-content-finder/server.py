from dotenv import load_dotenv

load_dotenv()

import httpx
import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Dict, Any
from datetime import datetime

from core.state import WorkflowState
from core.graph import graph
from utils.utils import save_results_to_json, clean_text_fields
from storage import pending_validations  # Import from storage module

app = FastAPI(
    title="Content Finder Agent",
    description="Agent for finding and analyzing content keywords",
    version="1.0.0"
)

class SearchTerms(BaseModel):
    terms: List[str]

class KeywordSelectionRequest(BaseModel):
    selected_keyword: str

class ContentFinderResponse(BaseModel):
    success: bool
    keywords_data: Dict[str, Any]
    router_response: Dict[str, Any] = None
    error: str = None


ROUTER_AGENT_URL = os.getenv("ROUTER_AGENT_URL", "http://router-agent:8080")


async def call_router_agent(keywords_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Call the router-agent with the processed keywords data
    """
    try:
        # Transform the data to match router-agent's expected format
        router_payload = {
            "keywords_data": keywords_data
        }

        print(f"Calling router-agent at {ROUTER_AGENT_URL}/route")

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{ROUTER_AGENT_URL}/route",
                json=router_payload,
                headers={"Content-Type": "application/json"}
            )

            if response.status_code == 200:
                router_result = response.json()
                print(f"Router-agent responded successfully: {router_result.get('routing_decision', 'Unknown')}")
                return router_result
            else:
                print(f"❌ Router-agent error: {response.status_code} - {response.text}")
                return {
                    "success": False,
                    "error": f"Router agent error: {response.status_code}"
                }

    except httpx.TimeoutException:
        print("Router-agent timeout")
        return {
            "success": False,
            "error": "Router agent timeout"
        }
    except Exception as e:
        print(f"❌ Error calling router-agent: {e}")
        return {
            "success": False,
            "error": f"Router agent connection error: {str(e)}"
        }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "content-finder-agent",
        "router_agent_url": ROUTER_AGENT_URL
    }


@app.get("/pending-validations")
async def get_pending_validations():
    """Get all pending validations for HIL dashboard"""
    try:
        pending_list = []
        for validation_id, validation_info in pending_validations.items():
            if validation_info.get("status") == "pending":
                pending_list.append({
                    "validation_id": validation_id,
                    "data": validation_info["data"],
                    "created_at": validation_info.get("created_at"),
                    "source_agent": "content-finder"
                })

        print(f"[HIL] 📋 Returning {len(pending_list)} pending validations")
        return {
            "success": True,
            "pending_validations": pending_list,
            "count": len(pending_list)
        }
    except Exception as e:
        print(f"❌ Error getting pending validations: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving pending validations: {str(e)}"
        )


@app.post("/submit-validation")
async def submit_validation_response(request: dict):
    """Submit validation response from HIL dashboard"""
    try:
        validation_id = request.get("validation_id")
        response = request.get("response")

        if not validation_id or response is None:
            raise HTTPException(
                status_code=400,
                detail="validation_id and response are required"
            )

        if validation_id not in pending_validations:
            raise HTTPException(
                status_code=404,
                detail=f"Validation {validation_id} not found"
            )

        # Update validation status
        pending_validations[validation_id]["status"] = "completed"
        pending_validations[validation_id]["response"] = response
        pending_validations[validation_id]["completed_at"] = datetime.now().isoformat()

        print(f"✅ Validation response received: {validation_id} -> {response}")

        return {
            "success": True,
            "message": f"Validation response recorded for {validation_id}",
            "validation_id": validation_id,
            "response": response
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error submitting validation: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error submitting validation: {str(e)}"
        )


@app.post("/content-finder", response_model=ContentFinderResponse)
async def content_finder(search_terms: SearchTerms):
    """
    Main endpoint for content finding and routing
    """
    try:
        print(f"\nStarting content finder for terms: {search_terms.terms}")

        # Run the content finder workflow
        initial_state = WorkflowState(
            terms=search_terms.terms,
            keywords=[],
            filtered_keywords=[],
            deduplicated_keywords=[],
            keyword_data={},
            failed_terms=[],  # NEW
            no_data_reason="",  # NEW
            processing_stopped=False  # NEW
        )

        result = await graph.ainvoke(initial_state)

        # NEW: Check if processing was stopped
        if result.get("processing_stopped", False):
            print(f"\n⚠️ Processing stopped: {result.get('no_data_reason')}")

            # Return empty but valid structure
            empty_response = ContentFinderResponse(
                success=True,  # Still successful, just no data
                keywords_data={},
                router_response={
                    "success": True,
                    "routing_decision": "no_data",
                    "reason": result.get("no_data_reason"),
                    "failed_terms": result.get("failed_terms", [])
                }
            )
            return empty_response

        print("\n===== CLEANING RESULTS =====")
        cleaned_keywords_data = clean_text_fields(result["keyword_data"])

        # Only call router if we have data
        if cleaned_keywords_data:
            print("\n===== CALLING ROUTER AGENT =====")
            router_response = await call_router_agent(cleaned_keywords_data)
        else:
            router_response = {
                "success": True,
                "routing_decision": "no_data",
                "reason": "No keyword data to route"
            }

        # Save results locally (even if empty)
        save_results_to_json(cleaned_keywords_data)

        return ContentFinderResponse(
            success=True,
            keywords_data=cleaned_keywords_data,
            router_response=router_response
        )

    except Exception as e:
        print(f"❌ Error in content finder: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Content finder error: {str(e)}"
        )


@app.post("/continue-with-keyword/{validation_id}")
async def continue_with_keyword(validation_id: str, request: KeywordSelectionRequest):
    """Continue workflow with human-selected keyword"""
    try:
        selected_keyword = request.selected_keyword
        print(f"📝 Continuing workflow with selected keyword: {selected_keyword}")

        # Check if validation exists
        if validation_id not in pending_validations:
            raise HTTPException(
                status_code=404,
                detail=f"Validation {validation_id} not found"
            )

        validation_info = pending_validations[validation_id]

        if selected_keyword == "stop":
            print("🛑 Workflow stopped by user")
            return {
                "success": True,
                "message": "Workflow stopped by user request",
                "selected_keyword": selected_keyword,
                "validation_id": validation_id,
                "stopped": True
            }

        # Get the original workflow state
        original_state = validation_info.get("keyword_context", {}).get("state", {})

        # CRITICAL FIX: Filter keyword_data to only include selected keyword
        original_keyword_data = original_state.get("keyword_data", {})
        filtered_keyword_data = {}

        # Only keep the selected keyword's data
        if selected_keyword in original_keyword_data:
            filtered_keyword_data[selected_keyword] = original_keyword_data[selected_keyword]
            print(f"✅ Found data for selected keyword: {selected_keyword}")
        else:
            print(f"⚠️ No data found for selected keyword: {selected_keyword}")
            # Fallback: try to find similar keyword
            for kw, data in original_keyword_data.items():
                if selected_keyword.lower() in kw.lower() or kw.lower() in selected_keyword.lower():
                    filtered_keyword_data[selected_keyword] = data
                    print(f"✅ Using similar keyword data: {kw} -> {selected_keyword}")
                    break

        # Update state with ONLY the selected keyword
        updated_state = {
            **original_state,
            "selected_keyword": selected_keyword,
            "processing_stopped": False,
            "awaiting_keyword_selection": False,
            "validation_id": None,
            "no_data_reason": "",
            # CRITICAL: Only the selected keyword
            "deduplicated_keywords": [selected_keyword],
            "keyword_data": filtered_keyword_data  # ONLY selected keyword data
        }

        print(f"🔄 Resuming workflow from SERP analysis with keyword: {selected_keyword}")
        print(f"📊 Keyword data keys: {list(filtered_keyword_data.keys())}")

        # Continue the workflow from fetch_serp_data_node
        try:
            from serp_analysis.serp_analysis_nodes import fetch_serp_data_node
            from serp_analysis.enrich_node import enrich_results_node

            # Run SERP analysis - this should now only process the selected keyword
            serp_result = await fetch_serp_data_node(updated_state)

            # Run enrichment
            final_result = await enrich_results_node(serp_result)

            # Clean results
            cleaned_keywords_data = clean_text_fields(final_result["keyword_data"])

            print(f"🔍 Final keywords after processing: {list(cleaned_keywords_data.keys())}")

            # Verify we only have the selected keyword
            if len(cleaned_keywords_data) != 1 or selected_keyword not in cleaned_keywords_data:
                print(f"⚠️ Warning: Expected only '{selected_keyword}', but got: {list(cleaned_keywords_data.keys())}")

            # Save results
            save_results_to_json(cleaned_keywords_data)

            # Call router agent
            router_response = await call_router_agent(cleaned_keywords_data)

            # Clean up validation
            del pending_validations[validation_id]

            return {
                "success": True,
                "message": f"Workflow completed successfully with keyword: {selected_keyword}",
                "selected_keyword": selected_keyword,
                "validation_id": validation_id,
                "keywords_data": cleaned_keywords_data,
                "router_response": router_response
            }

        except Exception as workflow_error:
            print(f"❌ Error continuing workflow: {workflow_error}")
            return {
                "success": False,
                "error": f"Workflow continuation failed: {str(workflow_error)}",
                "selected_keyword": selected_keyword,
                "validation_id": validation_id
            }

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error continuing with keyword: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error continuing workflow: {str(e)}"
        )


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Content Finder Agent API",
        "health": "/health",
        "main_endpoint": "/content-finder"
    }


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=port,
        log_level="info"
    )
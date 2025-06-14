from dotenv import load_dotenv

load_dotenv()

import httpx
import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Dict, Any

from core.state import WorkflowState
from core.graph import graph
from utils.utils import save_results_to_json, clean_text_fields

app = FastAPI(
    title="Content Finder Agent",
    description="Agent for finding and analyzing content keywords",
    version="1.0.0"
)


class SearchTerms(BaseModel):
    terms: List[str]


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
            keyword_data={}
        )

        result = await graph.ainvoke(initial_state)

        print("\n===== CLEANING RESULTS =====")
        cleaned_keywords_data = clean_text_fields(result["keyword_data"])

        # Save results locally
        save_results_to_json(cleaned_keywords_data)

        print("\n===== CALLING ROUTER AGENT =====")

        # Call router-agent with the results
        router_response = await call_router_agent(cleaned_keywords_data)

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
from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import json
import logging
import os
import sys
from datetime import datetime

# Add src directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# Change relative imports to absolute imports
from models import ContentFinderOutput, RouterResponse
from agent import process_content_finder_output

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Content Router Agent",
    description="LangGraph-based content routing microservice",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "content-router-agent",
        "timestamp": datetime.now().isoformat(),
        "environment": os.getenv("ENVIRONMENT", "development")
    }


@app.post("/route", response_model=RouterResponse)
async def route_content(content_data: ContentFinderOutput):
    """
    Main endpoint for routing content based on Content Finder output

    Args:
        content_data: Output from Content Finder Agent

    Returns:
        RouterResponse with routing decision and payload
    """

    try:
        logger.info(f"Processing routing request for keyword: {content_data.get_primary_keyword()}")  # FIXED

        # Process through router agent
        result = await process_content_finder_output(content_data)

        if result["success"]:
            logger.info(f"Routing successful: {result['routing_decision']}")
            return RouterResponse(**result)
        else:
            logger.error(f"Routing failed: {result['error']}")
            raise HTTPException(status_code=500, detail=result["error"])

    except Exception as e:
        logger.error(f"Route endpoint error: {e}")
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
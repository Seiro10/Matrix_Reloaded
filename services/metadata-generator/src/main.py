"""
Metadata Generator Agent - Processes router data to generate article metadata
"""

import os
import logging
import uuid
from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from datetime import datetime

from models.metadata_models import MetadataResponse
from core.llm_service import get_llm
from core.metadata_generator import generate_metadata
from utils.csv_parser import parse_csv_input
from services.copywriter_client import forward_to_copywriter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Ensure directories exist
os.makedirs("logs", exist_ok=True)
os.makedirs("temp", exist_ok=True)

# Initialize FastAPI app
app = FastAPI(
    title="Metadata Generator Agent",
    description="Generates metadata for articles based on content analysis",
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
        "service": "metadata-generator-agent",
        "timestamp": datetime.now().isoformat(),
    }


@app.post("/generate-metadata", response_model=MetadataResponse)
async def generate_metadata_endpoint(
        file: UploadFile = File(...),
        background_tasks: BackgroundTasks = None,
        llm=Depends(get_llm)
):
    """
    Generate metadata from uploaded CSV file and forward to copywriter
    """
    session_id = f"metadata_{str(uuid.uuid4())[:8]}"

    try:
        # Read file content
        content = await file.read()

        # Save file to temp directory
        file_path = os.path.join("temp", f"{session_id}_{file.filename}")
        with open(file_path, "wb") as f:
            f.write(content)

        # Parse CSV
        input_data = parse_csv_input(content)
        keyword = input_data.keyword or 'unknown'
        logger.info(f"🔄 Processing metadata for keyword: {keyword}")

        # Generate metadata
        metadata = generate_metadata(input_data, llm)
        logger.info(f"✅ Generated metadata for: {keyword}")

        # Forward to copywriter
        logger.info(f"📤 Forwarding to copywriter for: {keyword}")
        copywriter_response = forward_to_copywriter(metadata, input_data, file_path)

        # Prepare response based on copywriter success
        if copywriter_response.get("success"):
            return MetadataResponse(
                success=True,
                session_id=session_id,
                message=f"Metadata generated and article created successfully for keyword: {keyword}",
                metadata=metadata,
                copywriter_response=copywriter_response.get("copywriter_response"),
                article_id=copywriter_response.get("article_id"),
                content=copywriter_response.get("content"),
                status=copywriter_response.get("status", "completed")
            )
        else:
            # Metadata generation succeeded but copywriter failed
            return MetadataResponse(
                success=False,  # Overall process failed
                session_id=session_id,
                message=f"Metadata generated but copywriter failed for keyword: {keyword}",
                metadata=metadata,
                error=copywriter_response.get("error", "Copywriter agent error"),
                copywriter_response=copywriter_response.get("copywriter_response"),
                status=copywriter_response.get("status", "failed")
            )

    except Exception as e:
        logger.error(f"❌ Error processing request: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "session_id": session_id,
                "message": "Error generating metadata",
                "error": str(e),
                "status": "error"
            }
        )


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8084))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        log_level="info"
    )
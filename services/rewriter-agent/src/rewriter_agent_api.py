"""
Rewriter Agent FastAPI Service
Provides API endpoints for the Rewriter Agent functionality
"""

from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional
import os
import tempfile
import logging
from datetime import datetime
import asyncio
import json
from pathlib import Path

# Import models and main rewriter functionality
from .models import (
    RewriterResponse,
    RewriterStatus,
    RewriterRequestBody,
    RewriterInput,
    CompetitorData
)
from .rewriter_agent_main import process_rewriter_request, parse_csv_input

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Rewriter Agent API",
    description="LangGraph-based article rewriting service",
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

# In-memory task tracking
active_tasks = {}


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "rewriter-agent",
        "timestamp": datetime.now().isoformat(),
        "environment": os.getenv("ENVIRONMENT", "development")
    }


@app.post("/rewrite/csv", response_model=RewriterResponse)
async def rewrite_from_csv(
        background_tasks: BackgroundTasks,
        file: UploadFile = File(...)
):
    """
    Rewrite article based on CSV input from Router Agent

    Args:
        file: CSV file with rewriter input data

    Returns:
        RewriterResponse with processing results
    """

    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV")

    try:
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.csv', delete=False) as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_csv_path = tmp_file.name

        logger.info(f"📄 Processing CSV file: {file.filename}")

        # Parse CSV to get keyword for session tracking
        try:
            input_data = parse_csv_input(tmp_csv_path)
            keyword = input_data.keyword
        except Exception as e:
            os.unlink(tmp_csv_path)
            raise HTTPException(status_code=400, detail=f"Invalid CSV format: {str(e)}")

        # Generate session ID
        session_id = f"rewriter_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{keyword.replace(' ', '_')}"

        # Initialize task tracking
        active_tasks[session_id] = {
            "status": "processing",
            "progress": "Starting rewriter workflow...",
            "started_at": datetime.now().isoformat(),
            "keyword": keyword,
            "url": input_data.url_to_rewrite
        }

        # Process in background
        background_tasks.add_task(
            process_rewriter_background,
            session_id,
            tmp_csv_path
        )

        return RewriterResponse(
            success=True,
            session_id=session_id,
            message=f"Rewriter workflow started for keyword: {keyword}"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error processing CSV upload: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/rewrite/json", response_model=RewriterResponse)
async def rewrite_from_json(
        background_tasks: BackgroundTasks,
        request: RewriterRequestBody
):
    """
    Rewrite article based on JSON input

    Args:
        request: Rewriter request data

    Returns:
        RewriterResponse with processing results
    """

    try:
        logger.info(f"🎯 Processing JSON request for keyword: {request.keyword}")

        # Generate session ID
        session_id = f"rewriter_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{request.keyword.replace(' ', '_')}"

        # Initialize task tracking
        active_tasks[session_id] = {
            "status": "processing",
            "progress": "Starting rewriter workflow...",
            "started_at": datetime.now().isoformat(),
            "keyword": request.keyword,
            "url": request.url_to_rewrite
        }

        # Convert to CSV format temporarily for processing
        csv_content = create_csv_from_json(request)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as tmp_file:
            tmp_file.write(csv_content)
            tmp_csv_path = tmp_file.name

        # Process in background
        background_tasks.add_task(
            process_rewriter_background,
            session_id,
            tmp_csv_path
        )

        return RewriterResponse(
            success=True,
            session_id=session_id,
            message=f"Rewriter workflow started for keyword: {request.keyword}"
        )

    except Exception as e:
        logger.error(f"❌ Error processing JSON request: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/rewrite/status/{session_id}", response_model=RewriterStatus)
async def get_rewrite_status(session_id: str):
    """
    Get status of rewriting process

    Args:
        session_id: Session ID from rewrite request

    Returns:
        RewriterStatus with current status
    """

    if session_id not in active_tasks:
        raise HTTPException(status_code=404, detail="Session not found")

    task_info = active_tasks[session_id]

    return RewriterStatus(
        session_id=session_id,
        status=task_info["status"],
        progress=task_info["progress"],
        errors=task_info.get("errors"),
        result=task_info.get("result")
    )


@app.get("/rewrite/sessions")
async def list_active_sessions():
    """List all active rewriter sessions"""
    return {
        "active_sessions": len(active_tasks),
        "sessions": [
            {
                "session_id": sid,
                "status": info["status"],
                "keyword": info.get("keyword"),
                "started_at": info["started_at"]
            }
            for sid, info in active_tasks.items()
        ]
    }


@app.delete("/rewrite/sessions/{session_id}")
async def cancel_rewriter_session(session_id: str):
    """Cancel an active rewriter session"""
    if session_id not in active_tasks:
        raise HTTPException(status_code=404, detail="Session not found")

    active_tasks[session_id]["status"] = "cancelled"
    active_tasks[session_id]["progress"] = "Cancelled by user"

    return {"message": f"Session {session_id} cancelled"}


async def process_rewriter_background(session_id: str, csv_file_path: str):
    """Background task to process rewriter request"""
    try:
        # Update status
        active_tasks[session_id]["progress"] = "Fetching original article..."

        # Process the rewriter request
        result = await process_rewriter_request(csv_file_path)

        # Update task status
        if result["success"]:
            active_tasks[session_id]["status"] = "completed"
            active_tasks[session_id]["progress"] = "Article rewritten and published successfully"
            active_tasks[session_id]["result"] = result
        else:
            active_tasks[session_id]["status"] = "failed"
            active_tasks[session_id]["progress"] = "Rewriter workflow failed"
            active_tasks[session_id]["errors"] = result.get("errors", [str(result.get("error", "Unknown error"))])

        active_tasks[session_id]["completed_at"] = datetime.now().isoformat()

    except Exception as e:
        logger.error(f"❌ Background task error for session {session_id}: {e}")
        active_tasks[session_id]["status"] = "failed"
        active_tasks[session_id]["progress"] = f"Error: {str(e)}"
        active_tasks[session_id]["errors"] = [str(e)]
        active_tasks[session_id]["completed_at"] = datetime.now().isoformat()

    finally:
        # Clean up temporary file
        try:
            os.unlink(csv_file_path)
        except:
            pass


def create_csv_from_json(request: RewriterRequestBody) -> str:
    """Convert JSON request to CSV format for processing"""
    import io
    import csv

    output = io.StringIO()

    # CSV headers
    headers = [
        'Url', 'KW', 'competition', 'Site', 'confidence', 'monthly_searches',
        'people_also_ask', 'forum',
        'position1', 'title1', 'url1', 'snippet1', 'content1', 'structure1', 'headlines1', 'metadescription1',
        'position2', 'title2', 'url2', 'snippet2', 'content2', 'structure2', 'headlines2', 'metadescription2',
        'position3', 'title3', 'url3', 'snippet3', 'content3', 'structure3', 'headlines3', 'metadescription3'
    ]

    writer = csv.writer(output)
    writer.writerow(headers)

    # Prepare competitor data
    competitor_data = {}
    for i, comp in enumerate(request.competitors[:3], 1):
        competitor_data[f'position{i}'] = comp.get('position', i)
        competitor_data[f'title{i}'] = comp.get('title', '')
        competitor_data[f'url{i}'] = comp.get('url', '')
        competitor_data[f'snippet{i}'] = comp.get('snippet', '')
        competitor_data[f'content{i}'] = comp.get('content', '')
        competitor_data[f'structure{i}'] = comp.get('structure', '')
        competitor_data[f'headlines{i}'] = ';'.join(comp.get('headlines', []))
        competitor_data[f'metadescription{i}'] = comp.get('metadescription', '')

    # Fill missing competitors with empty data
    for i in range(len(request.competitors) + 1, 4):
        for field in ['position', 'title', 'url', 'snippet', 'content', 'structure', 'headlines', 'metadescription']:
            competitor_data[f'{field}{i}'] = ''

    # Create data row
    row = [
        request.url_to_rewrite,
        request.keyword,
        'UNKNOWN',  # competition not provided in JSON
        request.site,
        request.confidence,
        request.monthly_searches,
        ';'.join(request.people_also_ask),
        ';'.join(request.forum),
    ]

    # Add competitor data
    for i in range(1, 4):
        row.extend([
            competitor_data[f'position{i}'],
            competitor_data[f'title{i}'],
            competitor_data[f'url{i}'],
            competitor_data[f'snippet{i}'],
            competitor_data[f'content{i}'],
            competitor_data[f'structure{i}'],
            competitor_data[f'headlines{i}'],
            competitor_data[f'metadescription{i}']
        ])

    writer.writerow(row)

    return output.getvalue()


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8081))
    uvicorn.run(
        "rewriter_agent_api:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
        reload=False
    )
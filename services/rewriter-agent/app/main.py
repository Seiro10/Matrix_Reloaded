from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
import os
import csv
import io
from pathlib import Path

from app.models import ArticleUpdateRequest, ArticleUpdateResponse, CSVUploadResponse
from app.agents.graph import create_article_rewriter_graph
from app.config import settings

app = FastAPI(title="Blog Article Rewriter", version="1.0.0")

# Initialize the LangGraph agent
article_rewriter_graph = create_article_rewriter_graph()


@app.post("/update-blog-article", response_model=ArticleUpdateResponse)
async def update_blog_article_pipeline(request: ArticleUpdateRequest):
    """
    Update a blog article using LangGraph agent workflow (JSON input)
    """
    try:
        # Create the input state for the LangGraph workflow
        input_state = {
            "article_url": request.article_url,
            "subject": request.subject,
            "additional_content": request.additional_content,
            "error": None,
            "status": "initialized",
            "final_html": "",
            "post_id": None,
            "original_html": None,
            "temp_file_path": None,
            "html_blocks": None,
            "updated_blocks": None,
            "reconstructed_html": None,
            "diagnostic": None,
            "generated_sections": None,
            "slug": None,
            "jwt_token": None,
            "memory": None
        }

        print(f"[PIPELINE] Processing article: {request.article_url}")
        print(f"[PIPELINE] Subject: {request.subject}")

        # Run the LangGraph workflow
        config = {"configurable": {"thread_id": "article_update"}}
        final_state = article_rewriter_graph.invoke(input_state, config)

        if final_state.get("error"):
            raise HTTPException(status_code=500, detail=final_state["error"])

        return ArticleUpdateResponse(
            message=f"✅ Article mis à jour avec succès (ID {final_state.get('post_id')})",
            updated_html=final_state.get("final_html", ""),
            post_id=final_state.get("post_id"),
            status="success"
        )

    except Exception as e:
        print(f"[ERROR] Pipeline failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")


@app.post("/update-blog-article-csv", response_model=CSVUploadResponse)
async def update_blog_article_from_csv(file: UploadFile = File(...)):
    """
    Update a blog article using CSV file upload (for router-agent compatibility)
    """
    try:
        print(f"[CSV] Received file: {file.filename}")

        # Read CSV content
        content = await file.read()
        csv_content = content.decode('utf-8')

        # Parse CSV
        csv_reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(csv_reader)

        if not rows:
            raise HTTPException(status_code=400, detail="CSV file is empty")

        # Extract data from first row (assuming single article per CSV)
        row = rows[0]

        # Map CSV columns to our format - EXACT logic from working Django code
        article_url = row.get('Url', '').strip()
        subject = row.get('KW', '').strip()

        # Combine all available content for additional_content
        additional_content_parts = []

        # Add competitor content if available
        for i in range(1, 4):  # positions 1-3
            content_key = f'content{i}'
            if row.get(content_key):
                additional_content_parts.append(f"Contenu concurrent {i}: {row[content_key]}")

        # Add people also ask
        if row.get('people_also_ask'):
            additional_content_parts.append(f"Questions fréquentes: {row['people_also_ask']}")

        additional_content = "\n\n".join(additional_content_parts)

        if not article_url or not subject:
            raise HTTPException(
                status_code=400,
                detail="CSV must contain 'Url' and 'KW' columns"
            )

        print(f"[CSV] Extracted - URL: {article_url}, Subject: {subject}")

        # Create the input state for the LangGraph workflow
        input_state = {
            "article_url": article_url,
            "subject": subject,
            "additional_content": additional_content,
            "error": None,
            "status": "initialized",
            "final_html": "",
            "post_id": None,
            "original_html": None,
            "temp_file_path": None,
            "html_blocks": None,
            "updated_blocks": None,
            "reconstructed_html": None,
            "diagnostic": None,
            "generated_sections": None,
            "slug": None,
            "jwt_token": None,
            "memory": None
        }

        # Run the LangGraph workflow
        config = {"configurable": {"thread_id": f"csv_update_{subject.replace(' ', '_')}"}}
        final_state = article_rewriter_graph.invoke(input_state, config)

        if final_state.get("error"):
            raise HTTPException(status_code=500, detail=final_state["error"])

        return CSVUploadResponse(
            session_id=f"csv_{subject.replace(' ', '_')}_{os.urandom(4).hex()}",
            message=f"✅ Article mis à jour avec succès (ID {final_state.get('post_id')})",
            updated_html=final_state.get("final_html", ""),
            post_id=final_state.get("post_id"),
            status="success",
            processed_url=article_url,
            processed_subject=subject
        )

    except Exception as e:
        print(f"[ERROR] CSV Pipeline failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")


@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "Blog Article Rewriter API is running"}


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8082,
        reload=True
    )
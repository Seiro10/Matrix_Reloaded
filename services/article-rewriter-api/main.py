from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import json
import os

from src.pipeline import update_blog_article_pipeline

app = FastAPI(title="Article Rewriter API", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/update-blog-article")
async def update_blog_article_endpoint(request: dict):
    """
    Update a blog article using the pipeline from AI-Copywriter
    """
    try:
        print(f"[API] Processing request for URL: {request.get('article_url')}")
        print(f"[API] Subject: {request.get('subject')}")

        # Validate required fields
        if not request.get('article_url') or not request.get('subject'):
            raise HTTPException(status_code=400, detail="Missing required fields: article_url and subject")

        # Convert request to dict format expected by the pipeline
        data = {
            "article_url": request["article_url"],
            "subject": request["subject"],
            "link": "dummy_link",  # Not used since we're not using SupaData
            "additional_content": request.get("additional_content", "")
        }

        # Call the pipeline
        result = update_blog_article_pipeline(data)

        if result.get("error"):
            raise HTTPException(status_code=500, detail=result["error"])

        return {
            "message": result["message"],
            "updated_html": result["updated_html"],
            "post_id": result.get("post_id"),
            "status": "success"
        }

    except Exception as e:
        print(f"[ERROR] API request failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")


@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "Article Rewriter API is running"}


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8085,
        reload=True
    )
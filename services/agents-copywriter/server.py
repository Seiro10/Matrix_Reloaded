from dotenv import load_dotenv
load_dotenv(override=True)

from fastapi import FastAPI, Request, APIRouter
from workflow.pipeline import run_full_article_pipeline  # Now sync
from metadata_model import CopywriterRequest

app = FastAPI()

@app.post("/write_article")
def write_article(request: CopywriterRequest):  # Remove async
    """
    Updated endpoint to accept metadata from metadata-generator (SYNC VERSION)
    """
    article_id = run_full_article_pipeline(request)  # Remove await
    return {"status": "success", "wordpress_post_id": article_id}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "copywriter-agent"}
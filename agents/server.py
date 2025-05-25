from fastapi import FastAPI, Request
from workflow.pipeline import run_full_article_pipeline

app = FastAPI()

@app.post("/write_article")
async def write_article(request: Request):
    payload = await request.json()
    article_id = await run_full_article_pipeline(payload)
    return {"status": "success", "wordpress_post_id": article_id}

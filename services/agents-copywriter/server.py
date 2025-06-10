from dotenv import load_dotenv
load_dotenv(override=True)


from fastapi import FastAPI, Request, APIRouter
from workflow.pipeline import run_full_article_pipeline
from tests.test_writer_merge_post import run_from_merge_input

app = FastAPI()

@app.post("/write_article")
async def write_article(request: Request):
    payload = await request.json()
    article_id = await run_full_article_pipeline(payload)
    return {"status": "success", "wordpress_post_id": article_id}

# --------------------------
# 👇 Debug resume endpoint
# --------------------------
router = APIRouter()

@router.post("/resume_writer_from_saved_input")
def resume_writer():
    post_id = run_from_merge_input()
    return {"status": "done", "post_id": post_id}

# ✅ Register the router
app.include_router(router)


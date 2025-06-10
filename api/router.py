from fastapi import APIRouter
from agents.orchestrator import run_orchestration

router = APIRouter()

@router.post("/diagnose/")
async def diagnose(subject: str, article: str, transcript: str):
    result = run_orchestration(subject, article, transcript)
    return {"diagnosis": result}

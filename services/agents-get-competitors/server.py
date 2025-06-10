from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI
from typing import Dict, Any, List

from core.graph import build_workflow

app = FastAPI()

@app.post("/process-keywords")
async def process_keywords(request: List[Dict[str, Any]]):
    input_data = request

    initial_state = {
        "input_json": input_data,
        "urls_to_process": [],
        "processed": []
    }

    workflow = build_workflow()
    result = await workflow.ainvoke(initial_state)

    return {
        "status": "success",
        "processed_count": len(result.get("processed", [])),
        "results": result.get("processed", [])
    }
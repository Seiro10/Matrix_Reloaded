from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI, HTTPException
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
from core.state import WorkflowState
from core.graph import graph
import json
from pprint import pprint
from utils.utils import save_results_to_json, send_to_claude_direct_api


app = FastAPI()

class SearchTerms(BaseModel):
    terms: List[str]


@app.post("/content-finder")
async def content_finder(search_terms: SearchTerms):
    initial_state = WorkflowState(
        terms=search_terms.terms,
        keywords=[],
        filtered_keywords=[],
        deduplicated_keywords=[],
        keyword_data={}
    )
    result = await graph.ainvoke(initial_state)

    print("\n===== ENVOI À CLAUDE POUR NETTOYAGE =====\n")
    cleaned = await send_to_claude_direct_api(result["keyword_data"])

    save_results_to_json(cleaned)

    return cleaned

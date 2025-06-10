from dotenv import load_dotenv
load_dotenv()  # Très important ici

from fastapi import FastAPI
from pydantic import BaseModel
from typing import List

from core.state import WorkflowState
from core.graph import graph
from utils.utils import save_results_to_json, clean_text_fields

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

    print("\n===== ENVOI POUR NETTOYAGE =====\n")
    cleaned = clean_text_fields(result["keyword_data"])

    save_results_to_json(cleaned)
    return cleaned

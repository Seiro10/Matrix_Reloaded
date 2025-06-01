import os
from core.state import WorkflowState
from typing import List
from keywords_ideas.utils import get_keyword_ideas, load_google_ads_client


def fetch_keywords_node(state: dict) -> dict:
    search_terms = state.get("terms", [])
    customer_id = os.getenv("GOOGLE_ADS_CUSTOMER_ID")

    if not customer_id:
        raise ValueError("Missing GOOGLE_ADS_CUSTOMER_ID in environment variables")

    google_ads_client = load_google_ads_client()
    all_keywords = []

    for term in search_terms:
        try:
            ideas = get_keyword_ideas(google_ads_client, term, customer_id)
            all_keywords.extend(ideas)
        except Exception as e:
            print(f"[ERROR] Failed fetching KW for {term}: {e}")

    state["keywords"] = all_keywords
    return state



async def filter_keywords_node(state: WorkflowState) -> WorkflowState:
    raw_keywords = state.get("keywords", [])
    filtered = [kw["keyword"] for kw in raw_keywords if kw["competition"] == "LOW"]
    state["filtered_keywords"] = filtered[:50]
    return state


async def deduplicate_keywords_node(state: WorkflowState) -> WorkflowState:
    # Here you should call Claude via Anthropic API to deduplicate similar keywords.
    # For now, just return same list.
    state["deduplicated_keywords"] = list(set(state["filtered_keywords"]))
    return state



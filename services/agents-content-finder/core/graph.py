from langgraph.graph import StateGraph, START, END
from core.state import WorkflowState
from keywords_ideas.keywords_ideas_nodes_dataforseo import (
    fetch_keywords_node,
    filter_keywords_node,
    deduplicate_keywords_node,
    request_keyword_selection_node,  # ADD THIS IMPORT
)
from serp_analysis.serp_analysis_nodes import fetch_serp_data_node
from serp_analysis.enrich_node import enrich_results_node

workflow = StateGraph(WorkflowState)

# === Définition des nœuds
workflow.add_node("fetch_keywords", fetch_keywords_node)
workflow.add_node("filter_keywords", filter_keywords_node)
workflow.add_node("deduplicate_keywords", deduplicate_keywords_node)
workflow.add_node("request_keyword_selection", request_keyword_selection_node)  # ADD THIS NODE
workflow.add_node("fetch_serp_data", fetch_serp_data_node)
workflow.add_node("enrich_results", enrich_results_node)

# === Définition des transitions
workflow.add_edge(START, "fetch_keywords")
workflow.add_edge("fetch_keywords", "filter_keywords")
workflow.add_edge("filter_keywords", "deduplicate_keywords")
workflow.add_edge("deduplicate_keywords", "request_keyword_selection") 
workflow.add_edge("request_keyword_selection", "fetch_serp_data")
workflow.add_edge("fetch_serp_data", "enrich_results")
workflow.add_edge("enrich_results", END)

graph = workflow.compile()
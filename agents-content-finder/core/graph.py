from langgraph.graph import StateGraph, START, END
from core.state import WorkflowState
from keywords_ideas.keywords_ideas_nodes_dataforseo import (
    fetch_keywords_node,
    filter_keywords_node,
    deduplicate_keywords_node,
)
from serp_analysis.serp_analysis_nodes import fetch_serp_data_node

# === Graph complet (mots-clés + SERP)
workflow = StateGraph(WorkflowState)
workflow.add_node("fetch_keywords", fetch_keywords_node)
workflow.add_node("filter_keywords", filter_keywords_node)
workflow.add_node("deduplicate_keywords", deduplicate_keywords_node)
workflow.add_node("fetch_serp_data", fetch_serp_data_node)

workflow.add_edge(START, "fetch_keywords")
workflow.add_edge("fetch_keywords", "filter_keywords")
workflow.add_edge("filter_keywords", "deduplicate_keywords")
workflow.add_edge("deduplicate_keywords", "fetch_serp_data")
workflow.add_edge("fetch_serp_data", END)

graph = workflow.compile()


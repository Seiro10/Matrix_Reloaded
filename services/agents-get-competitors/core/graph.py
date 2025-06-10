from langgraph.graph import StateGraph, END
from typing import Dict, Any

from core.state import State
from datas_collector.datas_collector_nodes import extract_urls_per_kw
from scraper.scraper_nodes import scrape_all_urls


def build_workflow():
    graph = StateGraph(State)

    # Add nodes - BrightData returns clean data, so we don't need separate cleaning
    graph.add_node("extract", extract_urls_per_kw)
    graph.add_node("scrape_all", scrape_all_urls)

    # Set entry point and linear flow
    graph.set_entry_point("extract")
    graph.add_edge("extract", "scrape_all")
    graph.add_edge("scrape_all", END)

    return graph.compile()
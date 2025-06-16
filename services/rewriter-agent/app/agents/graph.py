from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from app.agents.state import ArticleRewriterState
from app.agents.nodes import (
    download_article_node,
    extract_slug_node,
    authenticate_wordpress_node,
    get_post_id_node,
    process_html_blocks_node,
    update_blocks_node,
    reconstruct_article_node,
    diagnose_missing_sections_node,
    generate_new_sections_node,
    merge_final_article_node,
    publish_to_wordpress_node
)


def should_continue_processing(state: ArticleRewriterState) -> str:
    """Determine if we should continue processing or handle an error"""
    if state.get("error"):
        return "error"
    return "continue"


def create_article_rewriter_graph():
    """Create the LangGraph workflow for article rewriting"""

    # Create the state graph
    workflow = StateGraph(ArticleRewriterState)

    # Add nodes
    workflow.add_node("download_article", download_article_node)
    workflow.add_node("extract_slug", extract_slug_node)
    workflow.add_node("authenticate_wordpress", authenticate_wordpress_node)
    workflow.add_node("get_post_id", get_post_id_node)
    workflow.add_node("process_html_blocks", process_html_blocks_node)
    workflow.add_node("update_blocks", update_blocks_node)
    workflow.add_node("reconstruct_article", reconstruct_article_node)
    workflow.add_node("diagnose_missing_sections", diagnose_missing_sections_node)
    workflow.add_node("generate_new_sections", generate_new_sections_node)
    workflow.add_node("merge_final_article", merge_final_article_node)
    workflow.add_node("publish_to_wordpress", publish_to_wordpress_node)

    # Add conditional edges with error handling
    workflow.add_edge(START, "download_article")
    workflow.add_conditional_edges(
        "download_article",
        should_continue_processing,
        {
            "continue": "extract_slug",
            "error": END
        }
    )

    workflow.add_conditional_edges(
        "extract_slug",
        should_continue_processing,
        {
            "continue": "authenticate_wordpress",
            "error": END
        }
    )

    workflow.add_conditional_edges(
        "authenticate_wordpress",
        should_continue_processing,
        {
            "continue": "get_post_id",
            "error": END
        }
    )

    workflow.add_conditional_edges(
        "get_post_id",
        should_continue_processing,
        {
            "continue": "process_html_blocks",
            "error": END
        }
    )

    workflow.add_conditional_edges(
        "process_html_blocks",
        should_continue_processing,
        {
            "continue": "update_blocks",
            "error": END
        }
    )

    workflow.add_conditional_edges(
        "update_blocks",
        should_continue_processing,
        {
            "continue": "reconstruct_article",
            "error": END
        }
    )

    workflow.add_conditional_edges(
        "reconstruct_article",
        should_continue_processing,
        {
            "continue": "diagnose_missing_sections",
            "error": END
        }
    )

    workflow.add_conditional_edges(
        "diagnose_missing_sections",
        should_continue_processing,
        {
            "continue": "generate_new_sections",
            "error": END
        }
    )

    workflow.add_conditional_edges(
        "generate_new_sections",
        should_continue_processing,
        {
            "continue": "merge_final_article",
            "error": END
        }
    )

    workflow.add_conditional_edges(
        "merge_final_article",
        should_continue_processing,
        {
            "continue": "publish_to_wordpress",
            "error": END
        }
    )

    workflow.add_edge("publish_to_wordpress", END)

    # Compile with memory
    checkpointer = MemorySaver()
    graph = workflow.compile(checkpointer=checkpointer)

    return graph
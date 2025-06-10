from langgraph.graph import StateGraph, END
from writing.writer_nodes import merge_sections_node, optimize_article_node

builder = StateGraph(dict)

# Nodes
builder.add_node("merge_sections", merge_sections_node)
builder.add_node("optimize_article", optimize_article_node)

# Graph flow
builder.set_entry_point("merge_sections")
builder.add_edge("merge_sections", "optimize_article")
builder.add_edge("optimize_article", END)

# Compile
writer_graph = builder.compile()


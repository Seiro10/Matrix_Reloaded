from langgraph.graph import StateGraph, END
from writing.writer_nodes import merge_sections_node

builder = StateGraph(dict)
builder.add_node("merge_sections", merge_sections_node)
builder.set_entry_point("merge_sections")
builder.add_edge("merge_sections", END)

writer_graph = builder.compile()

from langgraph.graph import StateGraph
from core.state import GraphState
from agents.writing.nodes import writer_node

def writing_node_service():
    builder = StateGraph(GraphState)
    builder.add_node("writing", writer_node())

    builder.set_entry_point("writing")
    graph = builder.compile()

    return graph

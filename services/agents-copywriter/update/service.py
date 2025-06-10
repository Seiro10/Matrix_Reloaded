from langgraph.graph import StateGraph
from core.state import GraphState
from agents.update.nodes import update_node

def build_graph_update():
    builder = StateGraph(GraphState)
    builder.add_node("update", update_node())

    builder.set_entry_point("update")
    graph = builder.compile()

    return graph

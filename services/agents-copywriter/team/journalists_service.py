from langgraph.graph import START, END, StateGraph
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from team.journalists_team import JournalistsSetup, Journalist, TeamOfJournalists
from team.journalists_nodes import build_team_of_journalists, human_feedback, should_continue

# Add nodes and edges
builder = StateGraph(JournalistsSetup)
builder.add_node("build_team_of_journalists", build_team_of_journalists)
builder.add_node("human_feedback", human_feedback)
builder.add_edge(START, "build_team_of_journalists")
builder.add_edge("build_team_of_journalists", "human_feedback")
builder.add_conditional_edges("human_feedback", should_continue, ["build_team_of_journalists", END])

# Compile
memory = MemorySaver()
journalist_team_graph = builder.compile(interrupt_before=['human_feedback'], checkpointer=memory)
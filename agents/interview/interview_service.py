from langgraph.graph import START, END, StateGraph
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import SystemMessage
from IPython.display import Image, display

from interview.interview import InterviewSession
from interview.interview_nodes import (
    ask_question,
    answer_question,
    save_interview,
    write_report_section,
    continue_or_finish,
)
from research.search_nodes import search_web, search_wikipedia

# Step 1: Build the interview LangGraph
interview_graph_builder = StateGraph(InterviewSession)

# Step 2: Define each node
interview_graph_builder.add_node("ask_question", ask_question)
interview_graph_builder.add_node("search_web", search_web)
interview_graph_builder.add_node("search_wikipedia", search_wikipedia)
interview_graph_builder.add_node("answer_question", answer_question)
interview_graph_builder.add_node("save_interview", save_interview)
interview_graph_builder.add_node("write_report_section", write_report_section)

# Step 3: Define transitions
interview_graph_builder.add_edge(START, "ask_question")
interview_graph_builder.add_edge("ask_question", "search_web")
interview_graph_builder.add_edge("ask_question", "search_wikipedia")
interview_graph_builder.add_edge("search_web", "answer_question")
interview_graph_builder.add_edge("search_wikipedia", "answer_question")

# Conditional loop: continue interview or end it
interview_graph_builder.add_conditional_edges(
    "answer_question",
    continue_or_finish,
    ["ask_question", "save_interview"]
)

interview_graph_builder.add_edge("save_interview", "write_report_section")
interview_graph_builder.add_edge("write_report_section", END)

# Step 4: Compile and export the graph
memory = MemorySaver()

interview_graph = interview_graph_builder.compile(
    checkpointer=memory
).with_config(run_name="journalists_interview_experts")

# Optional: visualize graph if using notebooks
# display(Image(interview_graph.get_graph().draw_mermaid_png()))

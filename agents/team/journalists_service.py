from dotenv import load_dotenv
load_dotenv()

from IPython.display import Image, display
from langgraph.graph import START, END, StateGraph
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from journalists_team import JournalistsSetup, Journalist, TeamOfJournalists
from journalists_nodes import build_team_of_journalists, human_feedback, should_continue

# Add nodes and edges
builder = StateGraph(JournalistsSetup)
builder.add_node("build_team_of_journalists", build_team_of_journalists)
builder.add_node("human_feedback", human_feedback)
builder.add_edge(START, "build_team_of_journalists")
builder.add_edge("build_team_of_journalists", "human_feedback")
builder.add_conditional_edges("human_feedback", should_continue, ["build_team_of_journalists", END])

# Compile
memory = MemorySaver()
graph = builder.compile(interrupt_before=['human_feedback'], checkpointer=memory)

# View
display(Image(graph.get_graph(xray=1).draw_mermaid_png()))

thread = {"configurable": {"thread_id": 3}}

# Step 1: Initial invocation
setup = graph.invoke({
    "topic": "Should You Play Black Desert Online in 2025?",
    "number_of_journalists": 3,
    "editor_feedback": None,
    "journalists": []  # Initial empty list
}, thread)

# Step 2: Print initial journalists
for journalist in setup['journalists']:
    print(journalist.profile)

# Step 3: Prompt for human feedback
user_feedback = input("Enter your editor feedback (or press Enter to skip): ").strip()

# Only update state if feedback is provided
if user_feedback:
    graph.update_state(
        thread,
        {"editor_feedback": user_feedback},
        as_node="human_feedback"
    )
else:
    print("No feedback provided. Skipping update.")


# Step 4: Continue the graph after feedback
for event in graph.stream(None, thread, stream_mode="values"):
    new_journalists = event.get('journalists', [])
    if new_journalists:
        for journalist in new_journalists:
            print(journalist.profile)

# Step 5: Clear feedback to avoid re-looping
graph.update_state(
    thread,
    {"editor_feedback": None},
    as_node="human_feedback"
)

# Step 6: Final execution (if needed) to reach END
graph.stream(None, thread, stream_mode="values")

# Step 7: Final state
final_state = graph.get_state(thread)

final_journalists = final_state.values.get('journalists', [])
for journalist in final_journalists:
    print(journalist.profile)

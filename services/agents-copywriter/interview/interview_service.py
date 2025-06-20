from langgraph.graph import START, END, StateGraph
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import SystemMessage
import concurrent.futures
import threading
from uuid import uuid4

from interview.interview import InterviewSession
from interview.interview_nodes import (
    ask_question,
    answer_question,
    save_interview,
    write_report_section,
    continue_or_finish,
)
from research.search_nodes import search_web

# Step 1: Build the interview LangGraph
interview_graph_builder = StateGraph(InterviewSession)

# Step 2: Define each node
interview_graph_builder.add_node("ask_question", ask_question)
interview_graph_builder.add_node("search_web", search_web)
interview_graph_builder.add_node("answer_question", answer_question)
interview_graph_builder.add_node("save_interview", save_interview)
interview_graph_builder.add_node("write_report_section", write_report_section)

# Step 3: Define transitions
interview_graph_builder.add_edge(START, "ask_question")
interview_graph_builder.add_edge("ask_question", "search_web")
interview_graph_builder.add_edge("search_web", "answer_question")

# Conditional loop: continue or save
interview_graph_builder.add_conditional_edges(
    "answer_question",
    continue_or_finish,
    ["ask_question", "save_interview"]
)

# After saving the conversation, write the report
interview_graph_builder.add_edge("save_interview", "write_report_section")
interview_graph_builder.add_edge("write_report_section", END)

# Step 4: Compile the graph
memory = MemorySaver()
interview_graph = interview_graph_builder.compile(
    checkpointer=memory
).with_config(run_name="journalists_interview_experts")


# NEW: Threading-based parallel interview function
def run_single_interview_sync(journalist, index, topic, audience, report_structure, max_turns=3):
    """
    Synchronous version of single interview for threading
    """
    try:
        from langchain_core.messages import HumanMessage

        print(f"[THREAD-{index}] 🚀 Starting interview with {journalist.full_name}")

        interview_state = InterviewSession(
            journalist=journalist,
            audience=audience,
            report_structure=report_structure,
            messages=[HumanMessage(content=f"Hello, I'm ready to discuss {topic}.")],
            max_turns=max_turns,
            sources=[],
            full_conversation="",
            report_sections=[]
        )

        interview_thread = {"configurable": {"thread_id": f"interview-{index}-{uuid4()}"}}
        result = interview_graph.invoke(interview_state, interview_thread)

        sections = result.get("report_sections", [])
        print(f"[THREAD-{index}] ✅ Interview completed with {len(sections)} sections")
        return sections

    except Exception as e:
        print(f"[THREAD-{index}] ❌ Interview failed: {e}")
        return []


def run_interviews_parallel_threaded(journalists, topic, audience, report_structure, max_turns=3):
    """
    Run multiple interviews in parallel using threading (better for EC2 with 2 cores)
    """
    print(f"[PARALLEL] 🧵 Starting {len(journalists)} interviews using ThreadPoolExecutor...")

    # Use ThreadPoolExecutor for I/O bound tasks (LLM calls)
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(journalists), 3)) as executor:
        # Submit all interviews
        future_to_journalist = {
            executor.submit(
                run_single_interview_sync,
                journalist,
                i,
                topic,
                audience,
                report_structure,
                max_turns
            ): (journalist, i)
            for i, journalist in enumerate(journalists)
        }

        # Collect results as they complete
        all_sections = []
        for future in concurrent.futures.as_completed(future_to_journalist):
            journalist, index = future_to_journalist[future]
            try:
                sections = future.result(timeout=300)  # 5 minute timeout per interview
                all_sections.extend(sections)
                print(f"[PARALLEL] ✅ Interview {index} completed successfully")
            except concurrent.futures.TimeoutError:
                print(f"[PARALLEL] ⏰ Interview {index} timed out")
            except Exception as e:
                print(f"[PARALLEL] ❌ Interview {index} failed: {e}")

    print(f"[PARALLEL] 🏁 All interviews completed. Total sections: {len(all_sections)}")
    return all_sections


# Keep the async version as fallback
async def run_interviews_parallel(journalists, topic, audience, report_structure, max_turns=3):
    """
    Fallback to threaded version for better compatibility
    """
    print("[PARALLEL] 🔄 Using threaded implementation for better performance...")
    return run_interviews_parallel_threaded(journalists, topic, audience, report_structure, max_turns)
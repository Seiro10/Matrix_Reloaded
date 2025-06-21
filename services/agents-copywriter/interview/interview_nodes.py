from dotenv import load_dotenv
import os

load_dotenv()
import ast

from interview.interview import InterviewSession
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, END, StateGraph
from langchain_core.messages import get_buffer_string

llm = ChatOpenAI(model="gpt-4o-mini")


def ask_question(state: InterviewSession):
    """Generates a question from the journalist to the expert, using assigned headlines."""

    # Get the journalist's assigned headlines
    assigned_headlines = getattr(state["journalist"], 'assigned_headlines', [])

    if not assigned_headlines:
        # Fallback to general question if no headlines assigned
        assigned_headlines = ["general topic discussion"]

    system_msg = SystemMessage(content=f"""
You are a journalist interviewing an expert about specific topics.

Your job is to ask clear and thoughtful questions to get helpful, surprising, and specific answers about the assigned headlines.

1. Surprising: Ask things that lead to interesting or non-obvious insights.
2. Specific: Avoid general talk, push for examples and real details.

Here is your profile:
{state["journalist"].profile}

You are specifically assigned to cover these headlines:
{', '.join(assigned_headlines)}

Focus your questions ONLY on these assigned headlines. Ask detailed questions about each headline to get comprehensive coverage.

Begin by introducing yourself in your journalist voice and ask your question about one of your assigned headlines.

Keep asking until you understand all your assigned headlines fully.

When you're done with all your assigned headlines, say: "Thank you so much for your help!" — this will end the interview.

Stay in character throughout the conversation.
""")

    # Generate the question using the LLM
    journalist_question = llm.invoke([system_msg] + state["messages"])

    # Return the new message to update the conversation
    return {"messages": [journalist_question]}


def answer_question(state: InterviewSession):
    """Expert reads the question and answers it using only the documents found in search."""

    # Get the journalist's assigned headlines for context
    assigned_headlines = getattr(state["journalist"], 'assigned_headlines', [])

    system_msg = SystemMessage(content=f"""
You are an expert being interviewed by an AI journalist.

Here is the journalist's profile:
{state["journalist"].profile}

The journalist is focusing on these specific headlines:
{', '.join(assigned_headlines)}

And here are documents you should use to answer the question:
{state["sources"]}

Format: 
1. Use only the info from the documents but rephrase all the informations to avoid plagiarism.
2. Don't guess or add anything new.
3. Start with a quick summary to give some context about the question.
4. Use paragraphs, lists and tables to make the content more digest
5. For each of them, explain in which aspect they are the best, and why the reader should consider buying it.
6. Write a conclusion to helps the reader with his decision
8. Reference documents using numbers like [1], [2].
9. List those sources at the bottom.
10. For example, write: [1] assistant/docs/mcp_guide.pdf, page 7.

""")
    expert_reply = llm.invoke([system_msg] + state["messages"])
    expert_reply.name = "expert"

    return {"messages": [expert_reply]}


def save_interview(state: InterviewSession):
    """Saves the full chat between journalist and expert as a plain text string."""

    conversation = get_buffer_string(state["messages"])
    return {"full_conversation": conversation}


def write_report_section(state: InterviewSession):
    """
    Writes a structured report based on a JSON layout (e.g., ranking article).
    """

    report_structure = state.get("report_structure")
    assigned_headlines = getattr(state["journalist"], 'assigned_headlines', [])

    system_msg = SystemMessage(content=f"""

    ## ROLE:
    You are a professional editorial writer specializing in product comparison articles, similar to those found on RTINGS.com.

    ## GOAL:
    Generate a structured article section focusing specifically on the assigned headlines. Your writing must be factual, objective, and informative. The output will be used to publish directly to a WordPress blog.

    ## ASSIGNED HEADLINES:
    Focus ONLY on these headlines: {', '.join(assigned_headlines)}

    ## INSTRUCTIONS:
    - Write in professional and journalistic style.
    - Add some personal experience you encountered using the product.
    - Maintain a neutral tone: no hype, no marketing fluff.
    - Follow the JSON format exactly.
    - Use interview content as your main source.
    - Use the documents only to back up claims (cite with [1], [2] if needed).
    - Use simple, engaging language fit for the audience: {state.get("audience", "general readers")}
    - Focus specifically on your assigned headlines, not the entire article structure.

    """)

    user_msg = HumanMessage(content=f"""
    --- STRUCTURE ---
    {report_structure}

    --- ASSIGNED HEADLINES ---
    {', '.join(assigned_headlines)}

    --- INTERVIEW TRANSCRIPT ---
    {state['full_conversation']}

    --- DOCUMENTS ---
    {state['sources']}

    Write content that specifically covers the assigned headlines above.
    """)

    response = llm.invoke([system_msg, user_msg])
    return {"report_sections": [response.content]}


def continue_or_finish(state: InterviewSession, name: str = "expert"):
    messages = state["messages"]
    max_turns = state.get("max_turns", 2)
    answers = [m for m in messages if isinstance(m, AIMessage) and m.name == name]

    print(f"[DEBUG] Expert answers so far: {len(answers)} / {max_turns}")

    if len(answers) >= max_turns:
        print("[DEBUG] Max turns reached, saving interview.")
        return "save_interview"

    last_question = messages[-2]
    if "Thank you so much for your help" in last_question.content:
        print("[DEBUG] Detected thank you message. Ending interview.")
        return "save_interview"

    print("[DEBUG] Continuing interview.")
    return "ask_question"
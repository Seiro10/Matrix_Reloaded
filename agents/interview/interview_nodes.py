from dotenv import load_dotenv
load_dotenv()

from interview.interview import InterviewSession
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, END, StateGraph
from langchain_core.messages import get_buffer_string

llm = ChatOpenAI(model="gpt-4o-mini")


def ask_question(state: InterviewSession):
    """Generates a question from the journalist to the expert, using the journalist's profile."""

    system_msg = SystemMessage(content=f"""
You are a journalist interviewing an expert about a specific topic.

Your job is to ask clear and thoughtful questions to get helpful, surprising, and specific answers.

1. Surprising: Ask things that lead to interesting or non-obvious insights.
2. Specific: Avoid general talk — push for examples and real details.

Here is your profile:
{state["journalist"].profile}

Begin by introducing yourself in your journalist voice and ask your question.

Keep asking until you understand the topic fully.

When you're done, say: "Thank you so much for your help!" — this will end the interview.

Stay in character throughout the conversation.""")

    # Generate the question using the LLM
    journalist_question = llm.invoke([system_msg] + state["messages"])

    # Return the new message to update the conversation
    return {"messages": [journalist_question]}


def answer_question(state: InterviewSession):
    """Expert reads the question and answers it using only the documents found in search."""

    system_msg = SystemMessage(content=f"""
You are an expert being interviewed by an AI journalist.

Here is the journalist's profile:
{state["journalist"].profile}

And here are documents you should use to answer the question:
{state["sources"]}

Format: 
1. Use only the info from the documents.
2. Don't guess or add anything new.
3. Start with a quick summary to give some context about the question.
4. Give your 5 choices and expand each of them based on the sources.
5. For each of them, explain in which aspect they are the best, and why the reader should consider buying it.
6. Write a conclusion to helps the reader with his decision
7. Write 2-5 questions/answers as a FAQ to answers common questions about the topic.
8. Reference documents using numbers like [1], [2].
9. List those sources at the bottom.
10. For example, write: [1] assistant/docs/mcp_guide.pdf, page 7.

Example:
Membrane keyboards offer a quiet, affordable alternative to mechanical models, while remaining high-performance for gamers. In this guide, we present a selection of the best membrane keyboards, combining comfort, responsiveness and attractive prices. Whether you're an occasional gamer or an enthusiast looking for a smooth, quiet keyboard, you'll find options here to suit your needs.
1. Razer Ornata V3 TKL
The Razer Ornata V3 TKL is a compact mechanical keyboard designed for gamers and users looking for a smooth, responsive typing experience...2. Turtle Beach Magma Le Turtle Beach Magma est un clavier gaming à membrane conçu pour offrir une expérience de jeu agréable à un prix abordable..
3. G213 Prodigy
The Logitech G213 RGB is a membrane gaming keyboard designed to offer a good compromise between performance and price...
...
Conclusion

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
    Writes a short report section based on the interview transcript,
    supported by any referenced source documents.
    """

    system_msg = SystemMessage(content=f"""
You are a technical writer creating a short report based on an interview with an expert.

Your job is to write a clear, engaging section using the interview transcript as the main source, 
while using the attached documents only to support factual claims with proper citations.

Here’s how to structure the report using Markdown:

## Title  
### Summary  (about 300 words)
### First choice (about 400 words)
### Second choice (about 400 words)
### Third choice (about 400 words)
...
### Conclusion (about 300 words)
### FAQ
### Sources

Writing instructions:
1. Use the interview transcript as your **primary source of insight**.
2. If a factual claim in the interview **can be confirmed by a document**, cite it using [1], [2], etc.
3. If a fact appears in the interview **but not in the documents**, it's okay to include it — just treat it as part of the expert's opinion.
4. Do **not** invent or assume anything beyond the transcript and the documents.
5. Keep the tone clear and concise. Avoid naming the expert or journalist.
7. In the “Sources” section, list each unique document used (no duplicates).
8. Use full links or filenames (e.g., [1] https://example.com or assistant/docs/mcp_guide.pdf, page 7).

Final review:
- Ensure Markdown structure is followed
- Make the title engaging and relevant to this focus area:
  **{state["journalist"].about}**""")

    # Provide both the documents and interview to the LLM
    user_msg = HumanMessage(content=f"""
Here are the materials you should use:

--- INTERVIEW TRANSCRIPT ---
{state["full_conversation"]}

--- DOCUMENTS FOR CITATION ---
{state["sources"]}
""")

    report = llm.invoke([system_msg, user_msg])
    return {"report_sections": [report.content]}


def continue_or_finish(state: InterviewSession, name: str = "expert"):
    """Decides if the interview should continue or end after each answer."""

    messages = state["messages"]
    max_turns = state.get("max_turns", 2)

    # Count how many times the expert has responded
    answers = [m for m in messages if isinstance(m, AIMessage) and m.name == name]

    if len(answers) >= max_turns:
        return "save_interview"

    # Check if the last journalist question said "thank you"
    last_question = messages[-2]
    if "Thank you so much for your help" in last_question.content:
        return "save_interview"

    return "ask_question"
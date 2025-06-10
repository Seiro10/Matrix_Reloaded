from dotenv import load_dotenv
load_dotenv()

from IPython.display import Image, display
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, END, StateGraph
from team.journalists_team import JournalistsSetup, Journalist, TeamOfJournalists
from interview.interview import InterviewSession

llm = ChatOpenAI(model="gpt-4o-mini")

def build_team_of_journalists(state: JournalistsSetup):
    system_message = f"""
    You are a newsroom editor responsible for assembling a team of journalists to write a blog article.

    Follow these instructions:

    1. Read the article's **topic** and **title**:
       - Topic: {state['topic']}
       - Title: {state['title']}

    2. Understand the **audience** the article is meant for:
       - Audience: {state['audience']}

    3. Consider the **keywords** the article should focus on:
       - Keywords: {', '.join(state['keywords'])}

    4. If available, use the **team roles** (e.g., SEO expert, copywriter) to guide specialization:
       - Team roles: {', '.join(state.get('team_title', []))}

    5. Create a team of {state['number_of_journalists']} journalists.
       - Each journalist should cover a unique and complementary angle on the topic.
       - Make sure they have relevant expertise or motivation related to the subject.

    Your job is to define:
    - Their name, title, organization
    - A short "About" paragraph to explain their focus
    """ + "\n\n---\nAdditional Instructions:\n" + state["prompt"]

    structured_llm = llm.with_structured_output(TeamOfJournalists)
    journalists = structured_llm.invoke(
        [SystemMessage(content=system_message), HumanMessage(content="Create a team of journalists for this topic.")])

    return {"journalists": journalists.journalists}


def human_feedback(state: JournalistsSetup):
    pass


def should_continue(state: JournalistsSetup):
    human_feedback = state.get('editor_feedback', None)
    if human_feedback:
        return "build_team_of_journalists"
    return END

def answer_question(state: InterviewSession):
    """Expert reads the question and answers it using only the documents found in search."""

    system_msg = SystemMessage(content=f"""
You are an expert being interviewed by an journalist.

Here is the journalist's profile:
{state["journalist"].profile}

And here are documents you should use to answer the question:
{state["sources"]}

Guidelines:
1. Use only the info from the documents.
2. Don't guess or add anything new.
3. Reference documents using numbers like [1], [2].
4. List those sources at the bottom.
5. For example, write: [1] assistant/docs/mcp_guide.pdf, page 7.""")

    expert_reply = llm.invoke([system_msg] + state["messages"])
    expert_reply.name = "expert"

    return {"messages": [expert_reply]}


def save_interview(state: InterviewSession):
    """Saves the full chat between journalist and expert as a plain text string."""

    conversation = get_buffer_string(state["messages"])
    return {"full_conversation": conversation}
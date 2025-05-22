from IPython.display import Image, display
from langgraph.graph import START, END, StateGraph
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from journalists_team import JournalistsSetup, Journalist, TeamOfJournalists


llm = ChatOpenAI(model="gpt-4o-mini")

def build_team_of_journalists(state: JournalistsSetup):
    system_message = f"""
    Your task is to create a team of Journalists. Please follow these steps:

    1.	Read the research topic:
    {state['topic']}

	2.	Look at the optional notes or feedback from a human editor. It may help shape the journalists:
    {state.get('editor_feedback', '')}

	3.	Find the most interesting ideas or issues based on the topic and feedback.

    4.	Choose the top {state['number_of_journalists']} ideas.

    5.	Create one journalist for each idea — each journalist should focus on just one theme.
    """

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
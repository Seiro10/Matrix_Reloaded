from typing import List
from typing_extensions import Annotated
from langgraph.graph import MessagesState
import operator
from team.journalists_team import Journalist


# Stores everything that happens during the chat between one journalist and one expert
class InterviewSession(MessagesState):
    max_turns: int                          # How many times the journalist and expert can go back and forth
    sources: Annotated[List, operator.add]  # All search results found during the chat (Tavely, Wiki, etc.)
    journalist: Journalist                  # The journalist who is asking the questions
    full_conversation: str                  # The full interview as plain text (what they talked about)
    report_sections: List[str]              # What the journalist wrote based on the interview (can be 1 or more sections)
    report_structure: dict                  # This is what we’ll use later to build the full report
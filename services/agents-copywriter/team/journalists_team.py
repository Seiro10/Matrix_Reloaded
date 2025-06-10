from typing import List
from typing_extensions import TypedDict
from pydantic import BaseModel, Field

class Journalist(BaseModel):
    organization: str = Field(
        description="Where the journalist works or is connected to.",
    )
    full_name: str = Field(
        description="The journalist's full name."
    )
    nickname: str = Field(
        description="The journalist's nickname."
    )
    job_title: str = Field(
        description="What the journalist does in this project or topic.",
    )
    about: str = Field(
        description="What the journalist cares about, what they focus on, or why they're involved.",
    )
    @property
    def profile(self) -> str:
        return f"""
Name: {self.full_name}
Nickname: {self.nickname}
Title: {self.job_title}
Organization: {self.organization}
About: {self.about}
        """

class TeamOfJournalists(BaseModel):
    journalists: List[Journalist] = Field(
        description="A list of people giving their input on the topic.",
    )


class JournalistsSetup(TypedDict):
    topic: str
    title: str
    type: str  # Guide, Review, Comparison, etc.
    keywords: List[str]
    team_title: List[str]  # Optional
    audience: str
    prompt: str  # Custom injected instruction
    number_of_journalists: int
    editor_feedback: str
    journalists: List[Journalist]

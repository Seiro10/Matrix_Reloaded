from langgraph.graph import StateGraph
from langchain_core.runnables import Runnable
from typing import TypedDict, Annotated
from agents.writing.diagnose_agent import diagnose_missing_sections
from agents.writing.writer_agent import generate_sections
from agents.publication.merge_agent import merge_sections
from typing import TypedDict, Optional, List
from agents.preprocessing.load_agent import LoadAgent
from agents.preprocessing.clean_agent import CleanAgent


class GraphState(TypedDict):
    subject: str
    article_url: str
    transcript_url: str
    article_html: Optional[str]
    transcript_text: Optional[str]
    reconstructed_html: Optional[str]
    diagnosis: Optional[str]
    generated_sections: Optional[str]
    merged_html: Optional[str]
    final_html: Optional[str]
    keywords: List[str]
    type: str
    last_modified: Optional[str]


def load_node():
    loader = LoadAgent()

    def _load(state: GraphState) -> GraphState:
        article_html = loader.fetch_html(state["article_url"])
        transcript_text = loader.fetch_html(state["transcript_url"])

        return {
            "subject": state["subject"],
            "article_url": state["article_url"],
            "transcript_url": state["transcript_url"],
            "keywords": state["keywords"],
            "type": state["type"],
            "last_modified": state["last_modified"],

            "article_html": article_html,
            "transcript_text": transcript_text,
            "reconstructed_html": None,
            "diagnosis": None,
            "generated_sections": None,
            "merged_html": None,
            "final_html": None,
        }

    return _load


def clean_node():
    cleaner = CleanAgent()

    def _clean(state: GraphState) -> GraphState:
        article_cleaned = cleaner.clean_html(state.get("article_html", ""))
        transcript_cleaned = cleaner.clean_html(state.get("transcript_text", ""))

        return {
            "subject": state.get("subject", ""),
            "article_url": state.get("article_url", ""),
            "transcript_url": state.get("transcript_url", ""),
            "article_html": article_cleaned,
            "transcript_text": transcript_cleaned,
            "reconstructed_html": state.get("reconstructed_html"),
            "diagnosis": state.get("diagnosis"),
            "generated_sections": state.get("generated_sections"),
            "merged_html": state.get("merged_html"),
            "final_html": state.get("final_html"),
            "keywords": state.get("keywords", []),
            "type": state.get("type", ""),
            "last_modified": state.get("last_modified")
        }

    return _clean



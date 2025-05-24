from pydantic import BaseModel, Field
from langchain_core.messages import get_buffer_string
from langchain_community.document_loaders import WikipediaLoader
from langchain_community.tools import TavilySearchResults

# A simple model to help the expert write a good search query
class SearchTask(BaseModel):
    search_text: str = Field(
        None,
        description="A short search query to help find useful information for the analyst’s question."
    )

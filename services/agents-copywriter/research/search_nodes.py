from langchain_community.tools import TavilySearchResults
from langchain_core.messages import get_buffer_string
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage
from interview.interview import InterviewSession
from langchain_openai import ChatOpenAI
from research.search import SearchTask

llm = ChatOpenAI(model="gpt-4o-mini")

search_prompt = SystemMessage(content=f"""
You are helping generate a search query for a web search.

You'll be given the full conversation between an journalist and an expert.  
Look at the entire discussion, and focus especially on the **last question** from the journalist.

Your task: Turn that question into a clear, well-structured search query.""")


def search_web(state: InterviewSession):

    structured_llm = llm.with_structured_output(SearchTask)
    search_query = structured_llm.invoke([search_prompt] + state["messages"])

    # Run Tavily search
    tavily_search = TavilySearchResults(max_results=5)
    results = tavily_search.invoke(search_query.search_text)

    # Safely format results
    formatted_docs = "\n\n---\n\n".join(
        [
            f'<Document/>\n{doc}\n</Document>' if isinstance(doc, str)
            else f'<Document href="{doc.get("url", "")}"/>\n{doc.get("content", str(doc))}\n</Document>'
            for doc in results
        ]
    )

    return {"sources": [formatted_docs]}
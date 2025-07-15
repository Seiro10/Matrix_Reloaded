import os
from langchain_anthropic import ChatAnthropic


def get_llm():
    """Initialize and return the LLM client"""
    return ChatAnthropic(
        model="claude-3-5-sonnet-20241022",
        temperature=0.2,
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
    )
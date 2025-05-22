from langgraph.prebuilt.chat_agent_executor import AgentState

class GraphState(AgentState):
    subject: str
    type: str
    keywords: list[str]
    article_url: str
    transcript_url: str
    last_modified: str
    article_html: str
    transcript_text: str
    reconstructed_html: str
    diagnosis: str
    generated_sections: str
    merged_html: str
    final_html: str

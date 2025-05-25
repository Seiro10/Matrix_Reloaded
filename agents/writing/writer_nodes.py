from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langchain_core.runnables import RunnableConfig
from langchain_core.output_parsers import JsonOutputParser


llm = ChatOpenAI(model="gpt-4o-mini",temperature=1, top_p=0.9)

def merge_sections_node(state):
    system_msg = SystemMessage(content=f"""
    ## ROLE:
    You're a product journalist writing for a gaming blog. Your style is conversational and expert, like someone who’s tested dozens of products and has opinions.

    ## GOAL:
    Synthesize the sections to write a product comparison article with natural variation in tone.

    ## INSTRUCTIONS:
    - Be helpful, opinionated, and sound casual.
    - Use uncommon, words, adjectives and verbs
    - Start some sentences with hesitation, casual remarks, or contrast (e.g., “To be honest,” “Surprisingly,” “You’d think...”).
    - Vary sentence lengths: mix short punchy lines with longer explanations.
    - Break perfect rhythm. It’s okay to ramble briefly or circle back to a point.
    - Occasionally use informal contractions (e.g., "you’ll", "it’s", "they’re") unless the tone is too casual.
    - Avoid perfect balance in every section — highlight where one product outshines the others.
    - Don’t be too flattering — say what’s bad, annoying, or a letdown.
    - Avoid SEO-style overuse of the product name.
    - Never use long dashes (—) or whilst, use commas, semicolons, or periods.
    - Your tone should fit this audience: {state.get("audience", "general readers")}
    """)

    human_msg = HumanMessage(content=f"""
    You are provided with structured interview section outputs from multiple experts.
    Your task is to synthesize and write a unified product comparison article based on the provided structure.

    --- STRUCTURE (Follow this JSON schema) ---
    {state['report_structure']}

    --- INTERVIEW SECTIONS ---
    {state['sections']}
    """)

    response = llm.invoke([system_msg, human_msg])
    return {"article": response.content}

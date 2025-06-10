from langgraph.graph import StateGraph
from core.state import GraphState
from langgraph.checkpoint.memory import InMemorySaver
from agents.preprocessing.load_agent import LoadAgent
from agents.preprocessing.nodes import clean_node

def load_node():
    loader = LoadAgent()

    def _load(state: GraphState) -> GraphState:
        print("[PREPROCESS] 🚀 Étape 1 : Chargement du HTML et transcript")
        article_html, transcript = loader.load(state["article_url"], state["transcript_url"])
        print(f"[PREPROCESS] 📄 HTML récupéré ({len(article_html)} caractères)")
        print(f"[PREPROCESS] 🎙️ Transcript récupéré ({len(transcript)} caractères)")
        return {
            **state,
            "article_html": article_html,
            "transcript_text": transcript,
        }

    return _load

def preprocessing_node():
    builder = StateGraph(GraphState)
    builder.add_node("load", load_node())
    builder.add_node("clean", clean_node())

    builder.set_entry_point("load")
    builder.add_edge("load", "clean")

    graph = builder.compile()
    return graph.with_config(checkpointer=InMemorySaver())

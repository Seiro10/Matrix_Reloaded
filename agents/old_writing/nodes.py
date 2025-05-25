from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage
from core.state import GraphState
from utils.html_blocks import extract_html_blocks
import logging

logger = logging.getLogger(__name__)

# LLM config
llm = ChatOpenAI(
    model="gpt-4.1-2025-04-14",
    temperature=1,
    top_p=0.95,
    frequency_penalty=0.5,
    presence_penalty=0.8
)

# Prompt HTML direct (pas de JSON)
prompt = ChatPromptTemplate.from_messages([
    ("system", """
Tu es un expert en contenu gaming. Tu reçois un article HTML divisé en blocs (chaque bloc a un <h2> suivi de contenu) et un transcript d'une vidéo récente sur le même sujet.

### OBJECTIF
- Pour chaque bloc HTML :
    - S'il est encore à jour et pertinent : laisse-le tel quel.
    - S'il est obsolète ou hors sujet : remplace-le directement par une nouvelle version corrigée.
- Tu peux ajouter des commentaires HTML `<!-- VALID -->`, `<!-- OUTDATED -->`, `<!-- OFF_TOPIC -->` avant chaque bloc pour signaler son statut.

### CONTRAINTES
- Ne rends que du HTML valide, sans texte explicatif ou JSON.
- Utilise uniquement les balises HTML : <h2>, <p>, <ul>, <li>, <strong>, <em>, <img>, <a>, <!-- commentaire -->
- Ne jamais utiliser de tirets longs (—), préfère : virgule, point ou point-virgule.
"""),
    ("human", "Transcript :\n\n{transcript}\n\nBlocs HTML à réviser :\n\n{blocks}")
])

# Chaîne LLM
llm_chain = prompt | llm

# LangGraph node
def update_node():
    def _diagnose(state: GraphState) -> GraphState:
        if not state.get("reconstructed_html"):
            raise ValueError("[ERROR] Le champ 'reconstructed_html' est vide.")

        # Extraire blocs HTML
        blocks = extract_html_blocks(state["reconstructed_html"])
        blocks_input = "".join([
            f"<h2>{b.get('title', '').text}</h2>" +
            "".join(str(e) for e in b["content"])
            for b in blocks
        ])

        logger.info(f"[DEBUG] {len(blocks)} blocs envoyés au LLM")

        # Appel LLM
        response = llm_chain.invoke({
            "transcript": state["transcript_text"],
            "blocks": blocks_input
        })

        # Résultat HTML directement utilisable
        updated_html = response.content.strip()

        logger.info("[DEBUG] ✅ LLM a généré une version révisée de l'article")

        return {
            **state,
            "diagnosis": updated_html
        }

    return _diagnose

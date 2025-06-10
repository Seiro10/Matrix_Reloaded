from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.exceptions import OutputParserException
from langchain_core.messages import AIMessage
from pydantic import BaseModel, RootModel
from typing import Literal, Optional, List
import re
import logging
from core.state import GraphState
from utils.html_blocks import extract_html_blocks

# === Pydantic Schema ===
class BlockDiagnosis(BaseModel):
    title: str
    status: Literal["VALID", "OUTDATED", "OFF_TOPIC"]
    reason: str
    updated_html: Optional[str]

class DiagnosisOutput(RootModel[List[BlockDiagnosis]]):
    pass

# === Nettoyage & extraction ===
def extract_json_block(text: str) -> str:
    match = re.search(r"```json\s*(\[.*\])\s*```", text, re.DOTALL)
    if match:
        return match.group(1)
    raise ValueError("❌ Aucun bloc JSON valide trouvé dans la réponse LLM.")

def fix_invalid_backslashes(text: str) -> str:
    cleaned = re.sub(r'\\(?!["\\/bfnrtu])', '', text)
    return extract_json_block(cleaned)

# === LLM Setup ===
parser = JsonOutputParser(pydantic_object=DiagnosisOutput)

llm = ChatOpenAI(
    model="gpt-4.1-2025-04-14",
    temperature=1,
    top_p=0.95,
    frequency_penalty=0.5,
    presence_penalty=0.8
)

prompt = ChatPromptTemplate.from_messages([
    ("system", f"""Tu es un expert en mise à jour d'articles gaming HTML. Tu dois diagnostiquer chaque bloc HTML d'un article, comparé à un transcript vidéo.

FORMAT attendu : {parser.get_format_instructions().replace('{', '{{').replace('}', '}}')}
- Retourne un JSON Markdown entre balises ```json
- Pas de backslashes dans le HTML
- Pas de texte hors du bloc JSON

Si un bloc est obsolète ou hors sujet, propose un champ `updated_html`.
"""),
    ("human", "Transcript :\n\n{transcript}\n\nBlocs HTML :\n\n{blocks}")
])

llm_chain = prompt | llm

# === Diagnostic node LangGraph ===
def update_node():
    def _diagnose(state: GraphState) -> GraphState:
        if not state.get("reconstructed_html"):
            raise ValueError("[ERROR] Le champ 'reconstructed_html' est vide.")

        blocks = extract_html_blocks(state["reconstructed_html"])
        blocks_input = [
            {
                "title": b.get("title", "").text if b.get("title") else "",
                "html": "".join(str(e) for e in b["content"])
            }
            for b in blocks
        ]

        # Appel du LLM
        llm_output = llm_chain.invoke({
            "transcript": state["transcript_text"],
            "blocks": blocks_input
        })

        try:
            cleaned = fix_invalid_backslashes(llm_output.content)
            parsed_output = parser.invoke(AIMessage(content=cleaned))
        except Exception as e:
            raise ValueError("Erreur de parsing JSON depuis le LLM. Vérifie le format retourné.") from e

        return {
            **state,
            "diagnosis": parsed_output
        }

    return _diagnose

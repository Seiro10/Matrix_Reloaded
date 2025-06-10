from agents.preprocessing.load_agent import LoadAgent
from langchain_openai import ChatOpenAI
from core.state import GraphState
from utils.cleaning import clean_html_for_processing, clean_transcript
from bs4 import BeautifulSoup
from utils.transcript import extract_video_id
from utils.file_io import save_html_to_file

llm = ChatOpenAI(model="gpt-4.1-2025-04-14", temperature=1, top_p=0.95, frequency_penalty=0.5, presence_penalty=0.8)


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


def clean_node():
    def _clean(state: GraphState) -> GraphState:
        print("[PREPROCESS] 🧼 Étape 2 : Nettoyage HTML & transcript")
        raw_html = state["article_html"]
        raw_transcript = state["transcript_text"]

        cleaned_html = clean_html_for_processing(raw_html)
        cleaned_transcript = clean_transcript(raw_transcript)

        # Sauvegarde HTML nettoyé
        video_id = extract_video_id(state["transcript_url"])
        save_html_to_file(cleaned_html, f"{video_id}.html")

        print(f"[PREPROCESS] ✅ HTML nettoyé ({len(cleaned_html)} caractères)")
        print(f"[PREPROCESS] ✅ Transcript nettoyé ({len(cleaned_transcript)} caractères)")

        return {
            **state,
            "article_html": cleaned_html,
            "transcript_text": cleaned_transcript,
        }

    return _clean

def neutralize_temporality_node():

    def _neutralize(state: GraphState) -> GraphState:
        subject = state["subject"]
        html = state["article_html"]
        title_text = state.get("diagnosis") or "Aucun"

        prompt = f"""
### CONTEXTE
Tu es un assistant spécialisé dans l'édition de contenu HTML lié aux jeux vidéo.

### OBJECTIF
Nettoyer le contenu HTML pour le rendre **pérenne et intemporel**.

### DONNÉES DE CONTEXTE
- Sujet de l'article : {subject}
- Titre de section : {title_text}

### RÈGLES
1. Supprime toutes les **références temporelles** précises si elles **ne sont pas explicitement présentes** dans le sujet ou le titre.
   - Exemples à retirer : années (2023, 2024), mois (mars, janvier), saisons (saison 14), patchs (1.19), périodes ("récemment", "il y a deux ans", "cette année", etc.)
2. Si une **référence temporelle est dans le sujet ou le titre**, tu peux la conserver mais elle doit être cohérente.
3. Supprime toute phrase incohérente ou inutile une fois la date retirée.
4. Préserve le ton d’origine et la structure HTML (<p>, <ul>, <strong>, etc.).
5. Écris en français uniquement.

### HTML À MODIFIER
{html}

### OUTPUT ATTENDU
Réponds uniquement avec le HTML nettoyé, sans aucun commentaire ou texte hors HTML.
"""

        try:
            response = llm.invoke(prompt)
            cleaned_html = response.content.strip()
            print("\n[NEUTRALIZE] ✅ HTML sans temporalité (500 premiers caractères) :\n")
            print(cleaned_html[:500])
            return {
                **state,
                "article_html": cleaned_html
            }
        except Exception as e:
            print(f"[NEUTRALIZE] ❌ Erreur lors du nettoyage de la temporalité : {e}")
            return state

    return _neutralize
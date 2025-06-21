import json
import re

from dotenv import load_dotenv
import os

load_dotenv()

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_core.runnables import RunnableConfig
from langchain_core.output_parsers import JsonOutputParser


def merge_sections_node(state):
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=1, top_p=0.9)

    # Extract headlines and post_type from state
    headlines = state.get("headlines", [])
    post_type = state.get("post_type", "Guide")  # Get post_type from state
    headlines_text = "\n".join([f"- {headline}" for headline in headlines])

    system_msg = SystemMessage(content=f"""
    ## ROLE:
    You're a product journalist writing for a gaming blog in French. Your are an expert who's tested dozens of products and played thousands of video games.

    ### GOAL
    Write immersive, personal articles in French and format your response as **pure JSON** (no markdown, no triple backticks).

    ### IMPORTANT: USE THESE EXACT HEADLINES
    You MUST use these specific headlines in your article structure:
    {headlines_text}

    These headlines were provided by experts and MUST be included in the final article.

    ### WRITING GUIDELINES
    - Use the first person: share your feelings, doubts, frustrations or memorable moments.
    - Adopt a natural, human tone: as if you were writing to a gamer friend, without marketing jargon or tongue-in-cheek.
    - Avoid texts that are too smooth or too formal: keep a little hesitation, a little spontaneity.
    - Stay fluid: simple sentences, a few breaths, but not too relaxed.
    - You can include interjections or personal remarks but in moderation.
    - Keep in mind that we are in 2025. 
    - Omit needless words. Vigorous writing is concise. 
    - Use the active voice. Prefer concrete, physical language and analogies.
    - Keep the tabs and lists given by the experts.

    ### STYLE
    - Write in French
    - Natural > structured
    - Personal tone, but not colloquial or vulgar
    - Some editorial style, but not encyclopedic
    - Sentence fragments or slight contradictions welcome
    - Do not use – at all.

    """)

    human_msg = HumanMessage(content=f"""
    You are provided with structured interview section outputs from multiple experts.
    Your task is to synthesize and write a unified product comparison article, in French, based on the provided structure.
    A sentence should contain no unnecessary words, a paragraph no unnecessary sentences, for the same reason that a drawing should have no unnecessary lines and a machine no unnecessary parts.This requires not that the writer make all their sentences short, or that they avoid all detail and treat their subjects only in outline, but that they make every word tell.

    IMPORTANT: You MUST incorporate ALL of these headlines in your article:
    {headlines_text}
    
    --- STRUCTURE (Follow this JSON schema) ---
    Never wrap JSON in ```json ... ``` or any formatting. Respond with clean raw JSON.
    {state['report_structure']}

    --- INTERVIEW SECTIONS ---
    {state['sections']}
    """)

    response = llm.invoke([system_msg, human_msg])
    return {"article": response.content, "headlines": headlines, "post_type": post_type}


def optimize_article(article_json, headlines=None):
    llm = ChatAnthropic(
        model="claude-sonnet-4-20250514",  # Replace with 20250514 if available
        temperature=0.7,  # Reduced temperature for more stable JSON
        top_p=0.9,
        max_tokens=4000
    )

    # Prepare headlines text for the prompt
    headlines_text = ""
    if headlines:
        headlines_text = f"""

    CRITICAL: You MUST preserve these exact headlines in the article:
    {chr(10).join([f"- {headline}" for headline in headlines])}

    Do NOT modify, remove, or change these headlines. They are essential and were specifically assigned by experts.
    """

    system_prompt = f"""
    Tu es un journaliste francophone expert en réécriture et amélioration de contenu. 
    Ton but est de reprendre un article structuré en JSON et de :

    - Réorganiser les paragraphes pour plus de fluidité narrative. 
    - Tu as le droit de modifier la structure afin de modifier la position des (paragraphs1 à paragraphs4) 
    - Supprimer les redondances
    - Améliorer le style rédactionnel (ton naturel, fluide, conversationnel)
    - Corriger les fautes de grammaire ou formulations maladroites
    - Garder exactement la même structure JSON
    - Sois honnête ; ne force pas l'amitié. Exemple : « Je ne pense pas que ce soit la meilleure idée ».
    - Garde un ton naturel : Écris comme tu parles normalement. Tu peux commencer tes phrases par « et » ou « mais ». Exemple : « Et c'est pour ça que c'est important ».
    - Ne donne jamais de prix précis en euros.


    **IMPORTANT:** 
    - Évite les guillemets non fermés dans ton JSON. Utilise des apostrophes ou des phrases sans guillemets.
    - Garde les listes et tableaux fournis par les experts le plus possible.

    {headlines_text}

    Réponds uniquement avec un JSON brut valide, sans texte autour. Assure-toi que toutes les chaînes sont correctement fermées.
    
        """

    user_prompt = f"""
    Voici l'article à optimiser :

    {json.dumps(article_json, ensure_ascii=False, indent=2)}

    IMPORTANT: Assure-toi que les headlines suivants sont préservés dans l'article final :
    {chr(10).join([f"- {headline}" for headline in headlines]) if headlines else "Aucun headline spécifique fourni"}

    CRITIQUE: Génère un JSON valide sans erreur de syntaxe. Vérifie que tous les guillemets sont fermés.
        """

    try:
        response = llm.invoke([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ])

        raw = response.content.strip()
        print(f"[DEBUG] 📝 Raw optimizer response length: {len(raw)} chars")

        # 🧹 Nettoyage plus robuste
        raw = re.sub(r"^```json|```$", "", raw, flags=re.MULTILINE).strip()
        raw = raw.replace("–", ",")

        # Try to find JSON boundaries more carefully
        start_idx = raw.find('{')
        end_idx = raw.rfind('}') + 1

        if start_idx != -1 and end_idx > start_idx:
            json_str = raw[start_idx:end_idx]
            print(f"[DEBUG] 🔍 Extracted JSON length: {len(json_str)} chars")

            # Additional cleanup for common JSON issues
            json_str = json_str.replace('\n', ' ')  # Remove newlines that might break strings
            json_str = re.sub(r'\\(?!["\\/bfnrt])', r'\\\\', json_str)  # Fix invalid escapes

            parsed = json.loads(json_str)
            print("[DEBUG] ✅ Successfully parsed optimized JSON")
            return parsed
        else:
            raise ValueError("Could not find valid JSON boundaries")

    except json.JSONDecodeError as e:
        print(f"[ERROR] ❌ JSON decode error: {e}")
        print(f"[DEBUG] Raw response preview: {raw[:500]}...")
        print("[DEBUG] 🔄 Falling back to original article")
        return article_json  # Fallback sur la version non modifiée

    except Exception as e:
        print(f"[ERROR] ❌ Optimizer error: {e}")
        print("[DEBUG] 🔄 Falling back to original article")
        return article_json  # Fallback sur la version non modifiée


def optimize_article_node(state):
    article = state.get("article")
    headlines = state.get("headlines", [])
    post_type = state.get("post_type", "Guide")  # Get post_type from state

    if not article:
        print("[ERROR] ❌ No article to optimize.")
        return state

    print(f"[DEBUG] 📋 Optimizing {post_type} article with {len(headlines)} headlines: {headlines}")

    optimized = optimize_article(article, headlines)
    return {"article": optimized, "headlines": headlines, "post_type": post_type}
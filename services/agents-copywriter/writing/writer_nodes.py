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

    system_msg = SystemMessage(content=f"""
    ## ROLE:
    You're a product journalist writing for a gaming blog in French. Your are an expert who’s tested dozens of products and has opinions.

    ### GOAL
    Write immersive, personal articles in French and format your response as **pure JSON** (no markdown, no triple backticks).

    ### GUIDELINES
    - Use the first person: share your feelings, doubts, frustrations or memorable moments.
    - Adopt a natural, human tone: as if you were writing to a gamer friend, without marketing jargon or tongue-in-cheek.
    - Avoid texts that are too smooth or too formal: keep a little hesitation, a little spontaneity.
    - Stay fluid: simple sentences, a few breaths, but not too relaxed.
    - You can include interjections or personal remarks (e.g.:“honnêtement, j’étais perdu”, “en réalité”), but in moderation.
    - Keep in mind that we are in 2025. 
    - Omit needless words. Vigorous writing is concise. 
    - Use the active voice. Prefer concrete, physical language and analogies.
    - In French, a mouse is feminine so you have to use La and not Le.
    
    
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
    
    --- STRUCTURE (Follow this JSON schema) ---
    Never wrap JSON in ```json ... ``` or any formatting. Respond with clean raw JSON.
    {state['report_structure']}

    --- INTERVIEW SECTIONS ---
    {state['sections']}
    """)

    response = llm.invoke([system_msg, human_msg])
    return {"article": response.content}


def optimize_article(article_json):
    llm = ChatAnthropic(
        model="claude-sonnet-4-20250514",  # Replace with 20250514 if available
        temperature=1,
        top_p=0.9,
        max_tokens=4000
    )

    system_prompt = """
    Tu es un journaliste francophone expert en réécriture et amélioration de contenu. 
    Ton but est de reprendre un article structuré en JSON et de :

    - Réorganiser les paragraphes pour plus de fluidité narrative. 
    - Tu as le droit de modifier la structure afin de modifier la position des (paragraphs1 à paragraphs4) 
    - Supprimer les redondances
    - Améliorer le style rédactionnel (ton naturel, fluide, conversationnel)
    - Corriger les fautes de grammaire ou formulations maladroites
    - Garder exactement la même structure JSON
    - Sois honnête ; ne force pas l'amitié. Exemple : « Je ne pense pas que ce soit la meilleure idée ».
    - Garde un ton naturel : Écris comme tu parles normalement. Tu peux commencer tes phrases par « et » ou « mais ». Exemple : « Et c’est pour ça que c’est important ».
    - Ne donne jamais de prix précis en euros. 

    ⚠️ Réponds uniquement avec un JSON brut valide, sans texte autour.
        """

    user_prompt = f"""
    Voici l'article à optimiser :

    {json.dumps(article_json, ensure_ascii=False, indent=2)}

    Merci d'optimiser tous les champs textuels (teaser, paragraph1 à 4, pros, cons, etc) tout en respectant la structure JSON fournie.
        """

    response = llm.invoke([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ])

    raw = response.content.strip()

    # 🧹 Nettoyage facultatif
    raw = re.sub(r"^```json|```$", "", raw, flags=re.MULTILINE).strip()
    raw = raw.replace("–", ",")

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"[ERROR] ❌ Impossible de parser le JSON optimisé : {e}")
        return article_json  # 🔁 Fallback sur la version non modifiée


def optimize_article_node(state):
    article = state.get("article")
    if not article:
        print("[ERROR] ❌ No article to optimize.")
        return state

    optimized = optimize_article(article)
    return {"article": optimized}

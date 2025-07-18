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
from writing.content_models import StructuredAffiliate, StructuredGuideNews, ContentBlock, StructuredSection


def merge_sections_node(state):
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.5, top_p=0.9)  # Température plus basse

    # Extract headlines and post_type from state
    headlines = state.get("headlines", [])
    post_type = state.get("post_type", "Guide")
    headlines_text = "\n".join([f"- {headline}" for headline in headlines])

    system_msg = SystemMessage(content=f"""
    ## ROLE:
    You're a product journalist writing for a gaming blog in French. You're an expert who's tested dozens of products.

    ### CRITICAL: RESPONSE FORMAT
    You MUST respond with a valid JSON object that follows this EXACT structure:
    {state['report_structure']}

    ### FORMATTING WITHIN JSON TEXT FIELDS:
    Inside the paragraph text, use these formatting techniques:

    **Bullet Lists**: Use this format inside paragraphs:
    ```
    "paragraph": "Introduction text.\n\nLes principales caractéristiques :\n- Point 1\n- Point 2\n- Point 3\n\nConclusion text."
    ```

    **Pros/Cons**: Use this format:
    ```
    "paragraph": "Description.\n\n**Avantages :**\n- ✅ Point positif 1\n- ✅ Point positif 2\n\n**Inconvénients :**\n- ❌ Point négatif 1"
    ```

    ### IMPORTANT: USE THESE EXACT HEADLINES
    You MUST use these specific headlines in your article structure:
    {headlines_text}

    ### WRITING STYLE:
    - First person, personal tone
    - Natural, conversational French
    - Share real testing experiences
    - Be honest about limitations
    - Mix formatting types within text for readability

    ### JSON VALIDATION:
    - Escape quotes properly with \"
    - No trailing commas
    - All strings must be properly closed
    - Return ONLY the JSON object, no markdown formatting around it
    """)

    human_msg = HumanMessage(content=f"""
    Create an article based on these interview sections.

    CRITICAL: Respond with ONLY a valid JSON object following this structure:
    {json.dumps(state['report_structure'], indent=2, ensure_ascii=False)}

    Headlines to include:
    {headlines_text}

    Interview sections:
    {state['sections']}

    Remember:
    1. Response must be valid JSON
    2. Include strategic formatting (lists, tables, pros/cons) WITHIN the paragraph text
    3. Use \\n for line breaks inside strings
    4. Escape quotes with \"
    5. No markdown code blocks around the JSON
    """)

    response = llm.invoke([system_msg, human_msg])

    # Clean the response to ensure it's valid JSON
    content = response.content.strip()

    # Remove any markdown formatting around JSON
    content = re.sub(r'^```json\s*', '', content)
    content = re.sub(r'\s*```$', '', content)

    # Try to parse and validate JSON
    try:
        parsed_article = json.loads(content)
        print("[DEBUG] ✅ Successfully parsed JSON from merge_sections_node")
        return {"article": parsed_article, "headlines": headlines, "post_type": post_type}
    except json.JSONDecodeError as e:
        print(f"[ERROR] ❌ JSON decode error in merge_sections_node: {e}")
        print(f"[DEBUG] Raw content preview: {content[:300]}...")

        # Fallback: try to fix common JSON issues
        fixed_content = fix_json_content(content)
        try:
            parsed_article = json.loads(fixed_content)
            print("[DEBUG] ✅ Successfully parsed fixed JSON")
            return {"article": parsed_article, "headlines": headlines, "post_type": post_type}
        except:
            print("[DEBUG] ❌ Could not fix JSON, returning raw content")
            return {"article": content, "headlines": headlines, "post_type": post_type}


def fix_json_content(content: str) -> str:
    """
    Try to fix common JSON formatting issues
    """
    # Remove trailing commas
    content = re.sub(r',(\s*[}\]])', r'\1', content)

    # Fix unescaped quotes in strings (basic attempt)
    # This is tricky and might need more sophisticated handling

    # Remove any non-JSON content at start/end
    start_idx = content.find('{')
    end_idx = content.rfind('}') + 1

    if start_idx != -1 and end_idx > start_idx:
        content = content[start_idx:end_idx]

    return content


def optimize_article(article_json, headlines=None):
    llm = ChatAnthropic(
        model="claude-sonnet-4-20250514",
        temperature=0.3,
        top_p=0.9,
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
    - Tu DOIS répondre avec un JSON complet et valide. JAMAIS de réponse partielle.

    {headlines_text}

    Réponds uniquement avec un JSON brut valide, sans texte autour. Assure-toi que toutes les chaînes sont correctement fermées.
    """

    user_prompt = f"""
    Voici l'article à optimiser :

    {json.dumps(article_json, ensure_ascii=False, indent=2)}

    IMPORTANT: Assure-toi que les headlines suivants sont préservés dans l'article final :
    {chr(10).join([f"- {headline}" for headline in headlines]) if headlines else "Aucun headline spécifique fourni"}

    CRITIQUE: Génère un JSON valide COMPLET sans erreur de syntaxe. Vérifie que tous les guillemets sont fermés.
    La réponse doit être complète et ne doit jamais s'arrêter au milieu.
    """

    try:
        response = llm.invoke([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ])

        raw = response.content.strip()
        print(f"[DEBUG] 📝 Raw optimizer response length: {len(raw)} chars")

        # Check if response seems truncated or incomplete
        if len(raw) < 100 or not raw.endswith('}'):
            print(f"[WARNING] ⚠️ Response seems incomplete (length: {len(raw)})")
            print(f"[DEBUG] Raw response: {raw}")
            print("[DEBUG] 🔄 Falling back to original article")
            return article_json

        # 🧹 Nettoyage plus robuste
        raw = re.sub(r"^```json|```$", "", raw, flags=re.MULTILINE).strip()
        raw = raw.replace("–", ",")

        # Try to find JSON boundaries more carefully
        start_idx = raw.find('{')
        end_idx = raw.rfind('}') + 1

        if start_idx != -1 and end_idx > start_idx:
            json_str = raw[start_idx:end_idx]
            print(f"[DEBUG] 🔍 Extracted JSON length: {len(json_str)} chars")

            # Validate JSON structure before parsing
            if not json_str.strip().endswith('}'):
                print("[WARNING] ⚠️ JSON doesn't end properly")
                print("[DEBUG] 🔄 Falling back to original article")
                return article_json

            # Additional cleanup for common JSON issues
            json_str = re.sub(r'\\(?!["\\/bfnrt])', r'\\\\', json_str)  # Fix invalid escapes

            parsed = json.loads(json_str)

            # Validate that the parsed result has the expected structure
            if not isinstance(parsed, dict) or len(parsed) < 2:
                print("[WARNING] ⚠️ Parsed JSON structure seems incomplete")
                print("[DEBUG] 🔄 Falling back to original article")
                return article_json

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

    # Use the retry mechanism instead of direct optimization
    optimized = optimize_article_with_retry(article, headlines)
    return {"article": optimized, "headlines": headlines, "post_type": post_type}


def optimize_article_with_retry(article_json, headlines=None, max_retries=2):
    """
    Optimize article with retry mechanism for failed attempts
    """
    for attempt in range(max_retries + 1):
        try:
            print(f"[DEBUG] 🔄 Optimization attempt {attempt + 1}/{max_retries + 1}")
            result = optimize_article(article_json, headlines)

            # Check if result is the same as input (fallback was used)
            if result == article_json:
                if attempt < max_retries:
                    print(f"[DEBUG] ⚠️ Fallback used, retrying...")
                    continue
                else:
                    print(f"[DEBUG] ⚠️ Max retries reached, using original article")
                    return article_json
            else:
                print(f"[DEBUG] ✅ Optimization successful on attempt {attempt + 1}")
                return result

        except Exception as e:
            print(f"[ERROR] ❌ Optimization attempt {attempt + 1} failed: {e}")
            if attempt < max_retries:
                print(f"[DEBUG] 🔄 Retrying...")
                continue
            else:
                print(f"[DEBUG] ⚠️ Max retries reached, using original article")
                return article_json

    return article_json
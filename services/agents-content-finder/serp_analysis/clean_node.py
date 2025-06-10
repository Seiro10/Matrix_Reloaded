from dotenv import load_dotenv

load_dotenv()

import os
import json
import re
from anthropic import AsyncAnthropic
from core.state import WorkflowState

# Configuration Claude
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)


async def clean_results_node(state: WorkflowState) -> WorkflowState:
    """
    Nettoie et formate les données SERP en utilisant Claude
    """
    keyword_data = state.get("keyword_data", {})

    if not keyword_data:
        print("[CLEAN] Aucune donnée à nettoyer")
        return state

    print("[CLEAN] Début du nettoyage des données avec Claude")

    try:
        # Traitement par batch pour éviter les timeouts
        cleaned_data = {}

        # Traite les mots-clés par groupe de 3 pour optimiser les appels API
        keywords = list(keyword_data.keys())
        batch_size = 3

        for i in range(0, len(keywords), batch_size):
            batch_keywords = keywords[i:i + batch_size]
            batch_data = {kw: keyword_data[kw] for kw in batch_keywords}

            print(f"[CLEAN] Traitement du batch {i // batch_size + 1}/{(len(keywords) + batch_size - 1) // batch_size}")

            cleaned_batch = await clean_batch_with_claude(batch_data)
            cleaned_data.update(cleaned_batch)

        state["keyword_data"] = cleaned_data
        print(f"[CLEAN] ✅ Nettoyage terminé pour {len(cleaned_data)} mots-clés")

    except Exception as e:
        print(f"[ERROR] ❌ Erreur lors du nettoyage: {e}")
        # En cas d'erreur, on garde les données originales
        print("[CLEAN] Conservation des données originales")

    return state


async def clean_batch_with_claude(batch_data: dict) -> dict:
    """
    Nettoie un batch de données avec Claude
    """

    # Création du prompt de nettoyage
    prompt = create_cleaning_prompt(batch_data)

    try:
        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=20000,
            temperature=0,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        # Extraction du JSON de la réponse
        response_text = response.content[0].text
        print(f"[DEBUG] Réponse Claude (premiers 500 chars): {response_text[:500]}")

        # Recherche du JSON dans la réponse
        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1

        if json_start == -1 or json_end == 0:
            print("[ERROR] Aucun JSON trouvé dans la réponse")
            print(f"[DEBUG] Réponse complète: {response_text}")
            raise Exception("Aucun JSON trouvé dans la réponse de Claude")

        json_str = response_text[json_start:json_end]
        print(f"[DEBUG] JSON extrait (derniers 200 chars): ...{json_str[-200:]}")

        # Tentative de parsing avec gestion d'erreur améliorée
        try:
            cleaned_data = json.loads(json_str)
            return cleaned_data
        except json.JSONDecodeError as e:
            print(f"[ERROR] JSON mal formaté à la position {e.pos}")
            print(f"[DEBUG] Contexte autour de l'erreur: {json_str[max(0, e.pos - 50):e.pos + 50]}")

            # Tentative de réparation automatique du JSON
            fixed_json = attempt_json_repair(json_str)
            if fixed_json:
                try:
                    cleaned_data = json.loads(fixed_json)
                    print("[SUCCESS] JSON réparé automatiquement")
                    return cleaned_data
                except:
                    pass

            # Si tout échoue, retourne les données originales
            print("[FALLBACK] Retour aux données originales pour ce batch")
            return batch_data

    except Exception as e:
        print(f"[ERROR] Erreur API Claude: {e}")
        print("[FALLBACK] Retour aux données originales pour ce batch")
        return batch_data


def attempt_json_repair(json_str: str) -> str:
    """
    Tentative de réparation automatique du JSON
    """
    try:
        # Supprime les caractères de contrôle et espaces en trop
        json_str = json_str.strip()

        # Supprime les trailing commas
        json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)

        # Assure-toi que le JSON se termine correctement
        if not json_str.endswith('}'):
            # Compte les { et } pour déterminer combien il en manque
            open_braces = json_str.count('{')
            close_braces = json_str.count('}')
            missing_braces = open_braces - close_braces

            if missing_braces > 0:
                json_str += '}' * missing_braces
                print(f"[REPAIR] Ajout de {missing_braces} accolades fermantes")

        return json_str

    except Exception as e:
        print(f"[REPAIR] Échec de la réparation: {e}")
        return None


def create_cleaning_prompt(data: dict) -> str:
    """
    Crée le prompt pour nettoyer les données SERP (générique pour toutes niches)
    """

    data_json = json.dumps(data, ensure_ascii=False, indent=2)

    prompt = f"""Tu es un expert en nettoyage de données web. Ton rôle est de SUPPRIMER UNIQUEMENT les éléments parasites tout en CONSERVANT INTÉGRALEMENT le contenu principal.

**RÈGLE ABSOLUE : NE TOUCHE A RIEN DANS LA PARTIE CONTENT**

**CONSERVE ABSOLUMENT TOUT :**
- keyword, competition, monthly_searches
- people_also_ask, people_also_search_for, forum  
- organic_results complets (position, title, url, snippet)
- total_results_found

**Pour le contenu enrichi, SUPPRIME UNIQUEMENT ces éléments parasites :**

**Règles de nettoyage:**

1. **Contenu (content):** 
   - Supprime les éléments de navigation, footer, header ou recommandantions en fin d'article

2. **Headlines:** 
   - Supprime les doublons
   - Garde seulement les titres pertinents au sujet
   - Maximum 10 headlines par page
   - Supprime les titres de navigation

4. **People Also Ask:**
   - Garde maximum 4 questions les plus pertinentes
   - Supprime les duplicatas et variations

5. **People Also Search For:**
   - Garde maximum 6 termes les plus pertinents
   - Supprime les mots génériques comme "gratuit", "mobile"

6. **Meta descriptions:**
   - Supprime les éléments marketing parasites

**TRÈS IMPORTANT:** 
- Retourne UNIQUEMENT du JSON valide
- Conserve la structure exacte
- Ne résume JAMAIS le contenu
- Supprime seulement les éléments de navigation/interface

**Données à nettoyer:**

```json
{data_json}
```

JSON avec contenu nettoyé (sans résumé):"""

    return prompt
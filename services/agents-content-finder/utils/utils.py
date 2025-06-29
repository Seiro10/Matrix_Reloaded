import os
import base64
import json
import requests
from typing import List, Dict
from datetime import date
from dateutil.relativedelta import relativedelta

from dotenv import load_dotenv
load_dotenv()

from anthropic import AsyncAnthropic


def fetch_keyword_data_from_dataforseo(terms: List[str], language_code="fr", location_code=2250) -> List[Dict]:
    """Appelle l'API /related_keywords/live et retourne les résultats filtrés"""

    url = "https://api.dataforseo.com/v3/dataforseo_labs/google/related_keywords/live"
    headers = {
        "Authorization": f"Basic {os.getenv('DATAFOR_SEO_TOKEN').strip()}",
        "Content-Type": "application/json"
    }

    payload = []
    for term in terms:
        payload.append({
            "keyword": term,
            "language_code": language_code,
            "location_code": location_code,
            "limit": 3,
            "sort_by": "keyword_data.search_volume"
        })

    try:
        print(f"[DEBUG] Sending request to: {url}")
        print(f"[DEBUG] Payload: {json.dumps(payload, indent=2)}")

        response = requests.post(url, headers=headers, json=payload)
        print(f"[DEBUG] Response status: {response.status_code}")
        print(f"[DEBUG] Response headers: {dict(response.headers)}")
        print(f"[DEBUG] Full response body: {response.text}")

        if response.status_code != 200:
            raise Exception(f"[DataForSEO ERROR] {response.status_code}: {response.text}")

        data = response.json()
        print(f"[DEBUG] Parsed JSON: {json.dumps(data, indent=2)}")

        all_keywords = []

        for i, task in enumerate(data.get("tasks", [])):
            print(f"[DEBUG] Processing task {i}: {task}")

            if task.get("status_code") != 20000:
                print(f"[WARNING] ⚠️ Task failed: {task.get('status_message')}")
                continue

            results = task.get("result", [])
            print(f"[DEBUG] Task {i} results: {results}")

            if not results:
                print(f"[DEBUG] No results for task {i}")
                continue

            # Check the structure of the first result
            if results:
                print(f"[DEBUG] First result structure: {json.dumps(results[0], indent=2)}")

            for item in results[0].get("items", []):
                keyword_info = item.get("keyword_data", {}).get("keyword_info", {})

                # ✅ Try multiple possible competition fields
                competition_raw = (
                        keyword_info.get("competition") or  # String value
                        keyword_info.get("competition_index") or  # Numeric value
                        item.get("competition") or  # Direct field
                        "UNKNOWN"
                )

                all_keywords.append({
                    "keyword": item.get("keyword_data", {}).get("keyword", ""),
                    "monthly_searches": keyword_info.get("search_volume", 0),
                    "competition": parse_competition_level(competition_raw)  # ✅ Parse properly
                })

                print(f"[DEBUG] Processed: {all_keywords[-1]}")

        print(f"[DEBUG] Final all_keywords: {all_keywords}")
        print(f"[SUMMARY] ✅ {len(all_keywords)} mots-clés récupérés")
        return all_keywords

    except Exception as e:
        print(f"[ERROR] ❌ fetch_keyword_data_from_dataforseo: {e}")
        import traceback
        traceback.print_exc()
        return []


def parse_competition_level(competition_value) -> str:
    """Parse competition level from DataForSEO response"""

    print(f"[DEBUG] Parsing competition value: {competition_value} (type: {type(competition_value)})")

    # If it's already a string, return it
    if isinstance(competition_value, str):
        result = competition_value.upper()
        print(f"[DEBUG] String competition: {result}")
        return result

    # If it's a number (competition_index)
    if isinstance(competition_value, (int, float)):
        if competition_value is None:
            result = "UNKNOWN"
        elif competition_value < 33:
            result = "LOW"
        elif competition_value < 66:
            result = "MEDIUM"
        else:
            result = "HIGH"

        print(f"[DEBUG] Numeric competition {competition_value} -> {result}")
        return result

    # Default fallback
    print(f"[DEBUG] Unknown competition type, defaulting to UNKNOWN")
    return "UNKNOWN"

# === SAVE TO JSON ===

def save_results_to_json(keyword_data: Dict, output_dir="output", filename="results.json"):
    """Sauvegarde les résultats dans un fichier JSON"""
    try:
        os.makedirs(output_dir, exist_ok=True)
        path = os.path.join(output_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(keyword_data, f, ensure_ascii=False, indent=2)
        print(f"[✅] Résultats sauvegardés dans : {path}")
    except Exception as e:
        print(f"[ERROR] ❌ Erreur lors de la sauvegarde: {e}")


# === CLEANING  ===

import re

def clean_text_fields(obj):
    """Nettoie récursivement les champs texte dans un objet JSON (dict ou list)"""
    if isinstance(obj, dict):
        return {k: clean_text_fields(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_text_fields(i) for i in obj]
    elif isinstance(obj, str):
        # Remplacement de tous les types d'espaces insécables
        cleaned = obj
        cleaned = cleaned.replace('\u00a0', ' ')   # espace insécable unicode
        cleaned = cleaned.replace('\xa0', ' ')     # espace insécable (ISO)
        cleaned = re.sub(r'\s+', ' ', cleaned)     # normalisation des espaces (inclut 4&nbsp;)
        cleaned = cleaned.strip()
        return cleaned
    else:
        return obj


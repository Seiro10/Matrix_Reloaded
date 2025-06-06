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
            "limit": 10,
            "sort_by": "keyword_data.search_volume"
        })

    try:
        response = requests.post(url, headers=headers, json=payload)
        print(f"[DEBUG] status = {response.status_code}")
        print(f"[DEBUG] body = {response.text[:300]}...")

        if response.status_code != 200:
            raise Exception(f"[DataForSEO ERROR] {response.status_code}: {response.text}")

        data = response.json()
        all_keywords = []

        for task in data.get("tasks", []):
            if task.get("status_code") != 20000:
                print(f"[WARNING] ⚠️ Task failed: {task.get('status_message')}")
                continue

            results = task.get("result", [])
            if not results:
                continue

            for item in results[0].get("items", []):
                all_keywords.append({
                    "keyword": item.get("keyword_data", {}).get("keyword", ""),
                    "monthly_searches": item.get("keyword_data", {}).get("keyword_info", {}).get("search_volume", 0),
                    "competition": parse_competition_level(item.get("keyword_data", {}).get("keyword_info", {}).get("competition", 0))
                })

        print(f"[SUMMARY] ✅ {len(all_keywords)} mots-clés récupérés")
        return all_keywords

    except Exception as e:
        print(f"[ERROR] ❌ fetch_keyword_data_from_dataforseo: {e}")
        return []


def parse_competition_level(index: int) -> str:
    if index is None:
        return "UNKNOWN"
    elif index < 33:
        return "LOW"
    elif index < 66:
        return "MEDIUM"
    else:
        return "HIGH"


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


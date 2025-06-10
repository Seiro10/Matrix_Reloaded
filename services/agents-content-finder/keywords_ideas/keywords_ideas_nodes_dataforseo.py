# keywords_ideas_nodes_dataforseo.py

import asyncio
from core.state import WorkflowState
from utils.utils import fetch_keyword_data_from_dataforseo


# === 1. Fetch keywords from DataForSEO ===
async def fetch_keywords_node(state: dict) -> dict:
    """Récupère les mots-clés depuis DataForSEO"""
    search_terms = state.get("terms", [])

    if not search_terms:
        print("[WARNING] ⚠️ Aucun terme de recherche fourni.")
        state["keywords"] = []
        return state

    all_keywords = []
    successful_terms = []
    failed_terms = []

    for term in search_terms:
        try:
            print(f"[INFO] 🔍 Recherche de mots-clés pour: {term}")
            keywords = fetch_keyword_data_from_dataforseo([term])

            if keywords:
                all_keywords.extend(keywords)
                successful_terms.append(term)
                print(f"[SUCCESS] ✅ {len(keywords)} mots-clés trouvés pour '{term}'")
            else:
                failed_terms.append(term)
                print(f"[WARNING] ⚠️ Aucun mot-clé trouvé pour '{term}'")

        except Exception as e:
            failed_terms.append(term)
            print(f"[ERROR] ❌ Échec pour '{term}': {e}")

    # Injection dans keyword_data : compétition + volume
    state["keyword_data"] = {
        kw["keyword"]: {
            "competition": kw["competition"],
            "monthly_searches": kw["monthly_searches"]
        }
        for kw in all_keywords
    }

    state["keywords"] = all_keywords
    state["successful_terms"] = successful_terms
    state["failed_terms"] = failed_terms

    print(f"[SUMMARY] 📊 Total: {len(all_keywords)} mots-clés récupérés")
    return state


async def filter_keywords_node(state: dict) -> dict:
    """Filtre les mots-clés selon les critères définis"""
    raw_keywords = state.get("keywords", [])

    if not raw_keywords:
        print("[WARNING] ⚠️ Aucun mot-clé à filtrer")
        state["filtered_keywords"] = []
        return state

    # Filtrage : faible concurrence + volume minimum
    filtered = []
    for kw in raw_keywords:
        competition = kw.get("competition", "HIGH")
        monthly_searches = kw.get("monthly_searches", 0)

        if competition == "LOW" and monthly_searches >= 30:
            filtered.append(kw["keyword"])

    # Limitation à 50 mots-clés maximum
    state["filtered_keywords"] = filtered[:50]

    print(f"[FILTER] 🔍 {len(filtered)} mots-clés après filtrage (sur {len(raw_keywords)} initiaux)")
    return state


async def deduplicate_keywords_node(state: dict) -> dict:
    """Supprime les doublons des mots-clés"""
    filtered_keywords = state.get("filtered_keywords", [])

    if not filtered_keywords:
        print("[WARNING] ⚠️ Aucun mot-clé filtré à dédupliquer")
        state["deduplicated_keywords"] = []
        return state

    # Déduplication tout en préservant l'ordre
    seen = set()
    deduplicated = []
    for keyword in filtered_keywords:
        if keyword.lower() not in seen:
            seen.add(keyword.lower())
            deduplicated.append(keyword)

    state["deduplicated_keywords"] = deduplicated

    duplicates_removed = len(filtered_keywords) - len(deduplicated)
    print(f"[DEDUP] 🔄 {len(deduplicated)} mots-clés uniques ({duplicates_removed} doublons supprimés)")

    return state
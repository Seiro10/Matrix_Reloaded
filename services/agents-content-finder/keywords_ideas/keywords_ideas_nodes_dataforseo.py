# keywords_ideas_nodes_dataforseo.py

import asyncio
from core.state import WorkflowState
from utils.utils import fetch_keyword_data_from_dataforseo
from storage import pending_validations


async def fetch_keywords_node(state: dict) -> dict:
    """Récupère les mots-clés depuis DataForSEO"""
    search_terms = state.get("terms", [])

    if not search_terms:
        print("[WARNING] ⚠️ Aucun terme de recherche fourni.")
        state.update({
            "keywords": [],
            "processing_stopped": True,
            "no_data_reason": "No search terms provided"
        })
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

    # NEW: Check if we have any keywords at all
    if not all_keywords:
        print("[STOP] 🛑 Aucun mot-clé trouvé pour tous les termes. Arrêt du processus.")
        state.update({
            "keywords": [],
            "keyword_data": {},
            "failed_terms": failed_terms,
            "processing_stopped": True,
            "no_data_reason": f"No keywords found for any terms: {', '.join(search_terms)}"
        })
        return state

    # Injection dans keyword_data : compétition + volume
    state["keyword_data"] = {
        kw["keyword"]: {
            "competition": kw["competition"],
            "monthly_searches": kw["monthly_searches"]
        }
        for kw in all_keywords
    }

    state.update({
        "keywords": all_keywords,
        "successful_terms": successful_terms,
        "failed_terms": failed_terms,
        "processing_stopped": False,
        "no_data_reason": ""
    })

    print(f"[SUMMARY] 📊 Total: {len(all_keywords)} mots-clés récupérés")
    return state


async def filter_keywords_node(state: dict) -> dict:
    """Filtre les mots-clés selon les critères définis"""

    if state.get("processing_stopped", False):
        print(f"[SKIP] ⏭️ Filtrage ignoré: {state.get('no_data_reason', 'Process stopped earlier')}")
        state["filtered_keywords"] = []
        return state

    raw_keywords = state.get("keywords", [])

    if not raw_keywords:
        print("[STOP] 🛑 Aucun mot-clé à filtrer. Arrêt du processus.")
        state.update({
            "filtered_keywords": [],
            "processing_stopped": True,
            "no_data_reason": "No keywords to filter"
        })
        return state

    # ✅ Accept LOW and UNKNOWN competition
    filtered = []
    for kw in raw_keywords:
        competition = kw.get("competition", "HIGH")
        monthly_searches = kw.get("monthly_searches", 0)

        # ✅ Accept both LOW and UNKNOWN competition
        if competition in ["LOW", "UNKNOWN"] and monthly_searches >= 30:
            filtered.append(kw["keyword"])
            print(f"[ACCEPT] ✅ '{kw['keyword']}' - {monthly_searches} searches, {competition} competition")
        else:
            print(f"[REJECT] ❌ '{kw['keyword']}' - {monthly_searches} searches, {competition} competition")

    if not filtered:
        print(
            "[STOP] 🛑 Aucun mot-clé ne passe les filtres (LOW/UNKNOWN competition + ≥30 searches). Arrêt du processus.")
        state.update({
            "filtered_keywords": [],
            "processing_stopped": True,
            "no_data_reason": f"No keywords passed filters (LOW/UNKNOWN competition + ≥30 volume) from {len(raw_keywords)} keywords"
        })
        return state

    # Limitation à 50 mots-clés maximum
    state["filtered_keywords"] = filtered[:50]

    print(f"[FILTER] 🔍 {len(filtered)} mots-clés après filtrage (sur {len(raw_keywords)} initiaux)")
    return state


async def request_keyword_selection_node(state: dict) -> dict:
    """Request human selection of primary keyword from filtered results"""

    print(f"[DEBUG] 🔍 Entering request_keyword_selection_node")
    print(f"[DEBUG] Current state keys: {list(state.keys())}")
    print(f"[DEBUG] Processing stopped: {state.get('processing_stopped', False)}")

    if state.get("processing_stopped", False):
        print(f"[SKIP] ⏭️ Sélection de mots-clés ignorée: {state.get('no_data_reason', 'Process stopped earlier')}")
        return state

    deduplicated_keywords = state.get("deduplicated_keywords", [])
    print(f"[DEBUG] 📝 Found {len(deduplicated_keywords)} deduplicated keywords: {deduplicated_keywords}")

    # TEMPORARY: Always trigger keyword selection for testing
    if len(deduplicated_keywords) == 0:
        print(f"[STOP] 🛑 No keywords to select from")
        return state

    print(f"[DEBUG] 🛑 FORCING keyword selection for ALL cases (testing)")

    # More than 0 keywords - request human selection
    from datetime import datetime
    import uuid
    from storage import pending_validations

    validation_id = f"keyword_selection_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

    validation_data = {
        "type": "keyword_selection",
        "keywords": deduplicated_keywords,
        "keyword_data": state.get("keyword_data", {}),
        "question": f"Sélectionnez le mot-clé principal parmi les {len(deduplicated_keywords)} options:",
        "options": deduplicated_keywords[:10]
    }

    validation_info = {
        "data": validation_data,
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        "keyword_context": {
            "all_keywords": deduplicated_keywords,
            "keyword_data": state.get("keyword_data", {}),
            "state": state
        }
    }

    pending_validations[validation_id] = validation_info

    print(f"[HIL] 🤔 Sélection de mot-clé requise - ID: {validation_id}")
    print(f"[HIL] 📋 {len(deduplicated_keywords)} mots-clés disponibles")
    print(f"[HIL] 🌐 Dashboard: GET /pending-validations")
    print(f"[HIL] 📝 Validation stockée: {validation_id}")
    print(f"[HIL] 📦 Pending validations count: {len(pending_validations)}")

    # CRITICAL: Make sure we stop the workflow
    updated_state = {
        **state,
        "processing_stopped": True,
        "no_data_reason": f"Human keyword selection required - validation ID: {validation_id}",
        "validation_id": validation_id,
        "awaiting_keyword_selection": True
    }

    print(f"[DEBUG] 🛑 Setting processing_stopped = True")
    print(f"[DEBUG] 📤 Returning updated state with processing_stopped: {updated_state.get('processing_stopped')}")

    return updated_state


async def deduplicate_keywords_node(state: dict) -> dict:
    """Supprime les doublons des mots-clés"""

    print(f"[DEBUG] 🔍 Entering deduplicate_keywords_node")

    if state.get("processing_stopped", False):
        print(f"[SKIP] ⏭️ Déduplication ignorée: {state.get('no_data_reason', 'Process stopped earlier')}")
        state["deduplicated_keywords"] = []
        return state

    filtered_keywords = state.get("filtered_keywords", [])
    print(f"[DEBUG] 📝 Filtered keywords to deduplicate: {filtered_keywords}")

    if not filtered_keywords:
        print("[STOP] 🛑 Aucun mot-clé filtré à dédupliquer. Arrêt du processus.")
        state.update({
            "deduplicated_keywords": [],
            "processing_stopped": True,
            "no_data_reason": "No filtered keywords to deduplicate"
        })
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
    print(f"[DEBUG] 📤 Deduplicated keywords: {deduplicated}")

    return state
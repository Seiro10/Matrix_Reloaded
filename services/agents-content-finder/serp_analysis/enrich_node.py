# serp_analysis/enrich_node.py
from dotenv import load_dotenv

load_dotenv()
import os
import httpx
from bs4 import BeautifulSoup

from core.state import WorkflowState
from utils.scraper import clean_html_text, extract_structure_tags

BRIGHT_DATA_API_KEY = os.getenv("BRIGHT_DATA_API_KEY")


async def enrich_results_node(state: WorkflowState) -> WorkflowState:
    # NEW: Check if processing was already stopped
    if state.get("processing_stopped", False):
        print(f"[SKIP] ⏭️ Enrichissement ignoré: {state.get('no_data_reason', 'Process stopped earlier')}")
        return state

    keyword_data = state.get("keyword_data", {})

    # NEW: Check if we have any data to enrich
    if not keyword_data:
        print("[STOP] 🛑 Aucune donnée SERP à enrichir. Arrêt du processus.")
        state.update({
            "processing_stopped": True,
            "no_data_reason": "No SERP data to enrich"
        })
        return state

    # NEW: Check if we have any valid organic results to enrich
    enrichable_keywords = 0
    total_urls_to_enrich = 0

    for keyword, data in keyword_data.items():
        if not data.get("error") and data.get("organic_results"):
            enrichable_keywords += 1
            # Count URLs that can be enriched (have valid URLs)
            valid_urls = [r for r in data["organic_results"] if r.get("url")]
            total_urls_to_enrich += len(valid_urls)

    if enrichable_keywords == 0:
        print("[STOP] 🛑 Aucun résultat organique valide à enrichir. Arrêt du processus.")
        state.update({
            "processing_stopped": True,
            "no_data_reason": "No valid organic results to enrich"
        })
        return state

    print(f"[ENRICH] Starting enrichment phase - {enrichable_keywords} keywords, {total_urls_to_enrich} URLs")

    enriched_count = 0
    failed_count = 0

    for keyword, data in keyword_data.items():
        # Skip keywords with errors or no organic results
        if data.get("error") or not data.get("organic_results"):
            print(f"[SKIP] Skipping '{keyword}': {data.get('error', 'No organic results')}")
            continue

        results = data.get("organic_results", [])
        print(f"[KEYWORD] Processing '{keyword}' - {len(results)} results")

        # Enrichit SEULEMENT les 3 premiers résultats (maintenant on n'en a que 3)
        for i, result in enumerate(results):
            url = result.get("url")
            if not url:
                print(f"[SKIP] No URL for result {i + 1}")
                continue

            print(f"[FETCH] Enriching {i + 1}/{len(results)}: {url}")

            try:
                raw = await fetch_page_content(url)
                if raw.get("error"):
                    print(f"[DEBUG] BrightData error: {raw['error']}")
                    result["enrichment_error"] = raw["error"]
                    failed_count += 1
                    continue

                html = raw.get("body", "")
                if not html or len(html.strip()) < 500:
                    print(f"[ERROR] HTML too short or empty for {url}")
                    result["enrichment_error"] = "HTML content too short or empty"
                    failed_count += 1
                    continue

                soup = BeautifulSoup(html, "html.parser")

                # Extract content and structure
                result["content"] = clean_html_text(html)
                result["structure"] = extract_structure_tags(html)
                result["headlines"] = [
                    h.get_text(strip=True) for h in soup.find_all(["h1", "h2"])
                    if h.get_text(strip=True)  # Only non-empty headlines
                ]

                # Extract meta description
                meta = soup.find("meta", attrs={"name": "description"})
                result["metadescription"] = meta["content"].strip() if meta and meta.get("content") else ""

                enriched_count += 1
                print(f"[SUCCESS] ✅ Enriched: {url}")

            except Exception as e:
                print(f"[ERROR] ❌ Enrichment failed for {url}: {e}")
                result["enrichment_error"] = str(e)
                failed_count += 1

    # NEW: Check if any enrichment was successful
    if enriched_count == 0:
        print("[STOP] 🛑 Aucun enrichissement réussi. Arrêt du processus.")
        state.update({
            "processing_stopped": True,
            "no_data_reason": f"No successful enrichments out of {total_urls_to_enrich} attempted URLs"
        })
        return state

    print(f"[ENRICHMENT SUMMARY] ✅ {enriched_count} successful, ❌ {failed_count} failed")
    state["keyword_data"] = keyword_data
    return state


async def fetch_page_content(url: str) -> dict:
    """
    Utilise BrightData Web Unlocker pour contourner les protections
    Plus rapide que DataForSEO (5-15 secondes au lieu de 5 minutes)
    """

    web_unlocker_url = "https://api.brightdata.com/request"

    headers = {
        "Authorization": f"Bearer {BRIGHT_DATA_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "zone": "web_unlocker",
        "url": url,
        "format": "raw"
    }

    try:
        print(f"[DEBUG] Sending request to BrightData Web Unlocker for: {url}")

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(web_unlocker_url, json=payload, headers=headers)

            print(f"[DEBUG] BrightData response status: {response.status_code}")

            if response.status_code == 200:
                html_content = response.text

                # Vérification que le contenu n'est pas vide
                if len(html_content.strip()) < 500:
                    return {"error": f"Content too short ({len(html_content)} chars)"}

                print(f"[DEBUG] Successfully fetched {len(html_content)} characters of HTML")
                return {"body": html_content}

            elif response.status_code == 403:
                # Si Web Unlocker bloque, essayer sans JavaScript
                print("[DEBUG] 403 error, retrying without JavaScript...")
                payload["render_js"] = False

                retry_response = await client.post(web_unlocker_url, json=payload, headers=headers)

                if retry_response.status_code == 200:
                    html_content = retry_response.text
                    if len(html_content.strip()) < 500:
                        return {"error": f"Content too short on retry ({len(html_content)} chars)"}
                    return {"body": html_content}
                else:
                    return {
                        "error": f"BrightData Web Unlocker failed on retry: {retry_response.status_code} - {retry_response.text[:200]}"}

            else:
                return {"error": f"BrightData Web Unlocker error: {response.status_code} - {response.text[:200]}"}

    except httpx.TimeoutException:
        return {"error": "BrightData Web Unlocker timeout (60s)"}
    except Exception as e:
        return {"error": f"BrightData Web Unlocker request failed: {str(e)}"}
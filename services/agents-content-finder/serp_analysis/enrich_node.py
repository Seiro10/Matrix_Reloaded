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
    keyword_data = state.get("keyword_data", {})
    print("[ENRICH] Starting enrichment phase")

    for keyword, data in keyword_data.items():
        results = data.get("organic_results", [])

        # Enrichit SEULEMENT les 3 premiers résultats (maintenant on n'en a que 3)
        for result in results:  # Plus besoin de [:3] car on limite déjà à 3 dans SERP
            url = result.get("url")
            if not url:
                continue

            print(f"[FETCH] Enriching: {url}")

            try:
                raw = await fetch_page_content(url)
                if raw.get("error"):
                    print(f"[DEBUG] BrightData error: {raw['error']}")
                    raise Exception(raw["error"])

                html = raw.get("body", "")
                soup = BeautifulSoup(html, "html.parser")

                result["content"] = clean_html_text(html)
                result["structure"] = extract_structure_tags(html)
                result["headlines"] = [
                    h.get_text(strip=True) for h in soup.find_all(["h1", "h2"])
                ]

                meta = soup.find("meta", attrs={"name": "description"})
                result["metadescription"] = meta["content"].strip() if meta and meta.get("content") else ""

                print(f"[SUCCESS] ✅ Enriched: {url}")

            except Exception as e:
                print(f"[ERROR] ❌ Enrichment failed for {url}: {e}")
                result["enrichment_error"] = str(e)

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
                    return {"body": retry_response.text}
                else:
                    return {
                        "error": f"BrightData Web Unlocker failed: {retry_response.status_code} - {retry_response.text[:200]}"}

            else:
                return {"error": f"BrightData Web Unlocker error: {response.status_code} - {response.text[:200]}"}

    except httpx.TimeoutException:
        return {"error": "BrightData Web Unlocker timeout (60s)"}
    except Exception as e:
        return {"error": f"BrightData Web Unlocker request failed: {str(e)}"}
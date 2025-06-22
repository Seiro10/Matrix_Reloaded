from dotenv import load_dotenv
load_dotenv()

import os
import httpx
import urllib.parse
import json
import asyncio
import re
from bs4 import BeautifulSoup
from core.state import WorkflowState

# === Config depuis .env ===
BRIGHT_DATA_API_KEY = os.getenv("BRIGHT_DATA_API_KEY")
BRD_ZONE = os.getenv("BRIGHTDATA_ZONE_NAME")


# === Node principal appelé par LangGraph ===
async def fetch_serp_data_node(state: WorkflowState) -> WorkflowState:
    updated_keyword_data = state.get("keyword_data", {})
    print("[DEBUG] keyword_data initial:", updated_keyword_data)

    for i, keyword in enumerate(state["deduplicated_keywords"]):
        try:
            print(f"[INFO] Processing keyword {i + 1}/{len(state['deduplicated_keywords'])}: '{keyword}'")

            response = await query_brightdata_serp_structured(keyword)

            if is_structured_response(response):
                print("[INFO] Got structured JSON response")
                keyword_entry = extract_serp_info(keyword, response)

            elif is_html_response(response):
                print("[INFO] Got HTML response, parsing...")

                # Récupère les métadonnées depuis keyword_data
                meta = updated_keyword_data.get(keyword, {})
                competition = meta.get("competition", "UNKNOWN")
                monthly_searches = meta.get("monthly_searches", 0)

                print(f"[DEBUG] competition for '{keyword}' = {competition}")
                print(f"[DEBUG] monthly searches for '{keyword}' = {monthly_searches}")

                keyword_entry = parse_html_serp(keyword, response, competition)

                # Injecte aussi le volume
                keyword_entry["monthly_searches"] = monthly_searches

            else:
                print(f"[EMPTY] No usable data for: {keyword}")
                updated_keyword_data[keyword] = {"error": "No data returned"}
                continue

            updated_keyword_data[keyword] = keyword_entry
            print(f"[SUCCESS] Extracted {len(keyword_entry.get('organic_results', []))} organic results")

        except Exception as e:
            print(f"[ERROR] Failed SERP fetch for '{keyword}': {e}")
            updated_keyword_data[keyword] = {"error": str(e)}

        if i < len(state["deduplicated_keywords"]) - 1:
            await asyncio.sleep(2)

    state["keyword_data"] = updated_keyword_data
    return state



# === BrightData Structured API
async def query_brightdata_serp_structured(keyword: str):
    url = "https://api.brightdata.com/datasets/google_search_results/snapshot"

    payload = {
        "dataset_id": "gd_l7q7dkf244hwjmtn06",
        "format": "json",
        "snapshot_query": {
            "url": f"https://www.google.com/search?q={urllib.parse.quote_plus(keyword)}",
            "country": "US",
            "language": "en"
        }
    }

    headers = {
        "Authorization": f"Bearer {BRIGHT_DATA_API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url, json=payload, headers=headers)

            if response.status_code == 200:
                return response.json()
            else:
                return await query_brightdata_proxy(keyword)

    except Exception as e:
        print(f"[DEBUG] Structured API failed, trying proxy: {e}")
        return await query_brightdata_proxy(keyword)


# === Fallback Proxy Request (HTML or JSON)
async def query_brightdata_proxy(keyword: str):
    url = "https://api.brightdata.com/request"
    encoded_keyword = urllib.parse.quote_plus(keyword)

    payload = {
        "zone": BRD_ZONE,
        "url": f"https://www.google.com/search?q={encoded_keyword}&hl=fr&gl=FR&lr=lang_fr",
        "format": "json"
    }

    headers = {
        "Authorization": f"Bearer {BRIGHT_DATA_API_KEY}",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(url, json=payload, headers=headers)

        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"BrightData proxy failed: {response.status_code}: {response.text}")


# === Check response format
def is_structured_response(response: dict) -> bool:
    return isinstance(response, dict) and "results" in response and isinstance(response["results"], list)


def is_html_response(response: dict) -> bool:
    return isinstance(response, dict) and "body" in response and "<html" in response["body"].lower()


# Dans serp_analysis/serp_analysis_nodes.py
# Modifie la fonction parse_html_serp

def parse_html_serp(keyword: str, response: dict, competition: str = "UNKNOWN") -> dict:
    html = response.get("body", "")
    soup = BeautifulSoup(html, 'html.parser')

    data = {
        "keyword": keyword,
        "competition": competition,
        "people_also_ask": [],
        "people_also_search_for": [],
        "forum": [],
        "organic_results": [],
        "total_results_found": 0
    }

    # Domaines exclus + Wikipedia et SensCritique
    excluded_domains = [
        'reddit.com', 'quora.com', 'youtube.com', 'stackoverflow.com',
        'github.com', 'discord.com', 'forum', 'community', 'discussion',
        'wikipedia.org', 'fr.wikipedia.org', 'en.wikipedia.org',  # Wikipedia
        'senscritique.com', 'www.senscritique.com'  # SensCritique
    ]

    snippet_selectors = [
        '[data-sncf]', '.VwiC3b', '.s3v9rd', '.st', '.lEBKkf', '[data-content-feature]'
    ]

    containers = soup.select('div[data-ved], div.g, div.yuRUbf, div.MjjYud')

    organic_results = []
    seen_urls = set()
    position = 1

    for container in containers:
        # Arrêter dès qu'on a 3 résultats
        if len(organic_results) >= 3:
            break

        try:
            title_elem = (container.find('h3') or
                          container.find(['div', 'span'], class_=re.compile(r'LC20lb|DKV0Md')) or
                          container.find('a'))
            if not title_elem:
                continue

            title = title_elem.get_text(strip=True)
            if not title or len(title) < 3:
                continue

            url_elem = container.find('a', href=True)
            if not url_elem:
                continue

            raw_url = url_elem['href']

            # Nettoyage des URLs Google / redirections
            if raw_url.startswith('/url?q='):
                try:
                    url = urllib.parse.parse_qs(urllib.parse.urlparse(raw_url).query).get('q', [''])[0]
                except:
                    continue
            elif raw_url.startswith('/search') or raw_url.startswith('#'):
                continue
            else:
                url = raw_url

            url = url.strip().split('&')[0]

            # Filtrage : domaines exclus (incluant Wikipedia et SensCritique)
            if any(domain in url.lower() for domain in excluded_domains):
                continue

            # Filtrage : déjà vu
            if url in seen_urls:
                continue
            seen_urls.add(url)

            # Snippet
            snippet = ""
            for selector in snippet_selectors:
                snippet_elem = container.select_one(selector)
                if snippet_elem:
                    snippet_text = snippet_elem.get_text(strip=True)
                    if snippet_text and len(snippet_text) > 20:
                        snippet = snippet_text
                        break

            if not snippet:
                parent = container.find_parent()
                if parent:
                    for selector in snippet_selectors:
                        snippet_elem = parent.select_one(selector)
                        if snippet_elem:
                            snippet_text = snippet_elem.get_text(strip=True)
                            if snippet_text and len(snippet_text) > 20:
                                snippet = snippet_text
                                break

            organic_results.append({
                "position": position,
                "title": title,
                "url": url,
                "snippet": snippet
            })

            position += 1

        except Exception as e:
            print(f"[DEBUG] Error parsing container: {e}")
            continue

    data["organic_results"] = organic_results
    data["total_results_found"] = len(organic_results)

    # === People Also Ask (PAA) ===
    paa = []
    for selector in ['[jsname="Cpkphb"]', '.related-question-pair', '[data-initq]']:
        for el in soup.select(selector):
            q = el.get_text(strip=True)
            if '?' in q and q not in paa:
                paa.append(q)
        if len(paa) >= 8:
            break
    data["people_also_ask"] = paa[:8]

    # === Related Searches ===
    # === Related Searches (filtrage FR+EN) ===
    related_searches = []

    # ✅ Terme à filtrer en anglais
    blacklist_en = {
        "see more", "view all", "sign in", "videos", "shopping",
        "short videos", "forums", "news", "images", "more results",
        "reddit", "tips", "ranked", "build", "guide", "next"
    }

    # ✅ Terme à filtrer en français (filtres UI, pas recherches liées)
    blacklist_fr = {
        "vidéos", "actualités", "vidéos courtes", "livres",
        "toutes les langues", "moins d'une heure", "moins de 24 heures",
        "moins d'une semaine", "outils", "filtrer", "langue",
        "images", "actualités", "plus de résultats", "moins d'un mois","moins d'un an",
        "mot à mot", "effacer", "voir plus", "suivant", "produits", "moins de 24 heures"
    }

    # ✅ Union blacklist
    blacklist_terms = blacklist_en.union(blacklist_fr)

    related_selectors = [
        '.brs_col a', '.k8XOCe a', '[data-ved] a[href*="/search"]',
        '.AaVjTc a', '.s75CSd a'
    ]

    for selector in related_selectors:
        links = soup.select(selector)
        for link in links:
            if link.get('href', '').startswith('/search'):
                text = link.get_text(strip=True).lower()
                if (
                        text and 3 < len(text) < 80 and '?' not in text and
                        not any(b in text for b in blacklist_terms) and
                        text not in related_searches and
                        text.lower() not in keyword.lower()
                ):
                    related_searches.append(text)

        if len(related_searches) >= 8:
            break

    data["people_also_search_for"] = related_searches[:8]

    # === Forum links ===
    forum_domains = ['reddit', 'quora', 'stackoverflow', 'forum']
    forum_links = []

    for link in soup.find_all('a', href=True):
        href = link['href'].strip()
        if any(domain in href for domain in forum_domains):
            if href.startswith("/search?") or not href.startswith("http"):
                continue
            if href not in forum_links:
                forum_links.append(href)

    data["forum"] = forum_links[:3]

    return data

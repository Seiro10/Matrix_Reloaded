import os
import httpx
import asyncio
import urllib.parse
from bs4 import BeautifulSoup
from core.state import State

BRIGHT_DATA_API_KEY = os.getenv("BRIGHT_DATA_API_KEY")
BRD_ZONE = os.getenv("BRIGHTDATA_ZONE_NAME")


async def process_entry(entry: dict) -> dict:
    url = entry.get("URL")
    if not url:
        return {**entry, "error": "Missing URL"}

    try:
        result = await fetch_page_content(url)
        if result.get("error"):
            return {**entry, "scraped_content": "", "error": result["error"]}

        html = result["body"]
        soup = BeautifulSoup(html, "html.parser")

        cleaned_text = soup.get_text(separator="\n", strip=True)
        word_count = len(cleaned_text.split())

        # 🔍 Structure HTML simplifiée
        structure_tags = []
        for tag in soup.find_all(["h1", "h2", "h3"]):
            structure_tags.append(str(tag))
        structure_html = "\n".join(structure_tags)

        # 📰 Headlines
        headlines = [tag.get_text(strip=True) for tag in soup.find_all(["h1", "h2"]) if tag.get_text(strip=True)]

        # 📝 Meta description
        meta_tag = soup.find("meta", attrs={"name": "description"})
        metadescription = meta_tag["content"].strip() if meta_tag and meta_tag.get("content") else ""

        return {
            **entry,
            "scraped_content": html,
            "Structure HTML": structure_html,
            "Headlines": headlines,
            "Metadescription": metadescription,
            "cleaned_text": cleaned_text,
            "word_count": word_count,
        }

    except Exception as e:
        return {**entry, "scraped_content": "", "error": str(e)}


async def scrape_all_urls(state: State) -> State:
    """
    Scrape toutes les URLs dans state["urls_to_process"] et stocke les résultats dans state["scraped"]
    """
    urls = state.get("urls_to_process", [])
    scraped = {}

    for i, entry in enumerate(urls):
        url = entry.get("URL")
        print(f"[{i + 1}/{len(urls)}] Scraping {url}")
        result = await process_entry(entry)
        scraped[url] = result

    state["scraped"] = scraped
    return state


async def fetch_page_content(url: str) -> dict:
    brightdata_url = "https://api.brightdata.com/request"

    payload = {
        "zone": BRD_ZONE,
        "url": url,
        "format": "raw"  # 🔁 ne pas mettre wait_for / render_js : Web Unlocker ne les accepte pas
    }

    headers = {
        "Authorization": f"Bearer {BRIGHT_DATA_API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(brightdata_url, json=payload, headers=headers)
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"BrightData API error: {response.status_code} - {response.text}"}
    except Exception as e:
        return {"error": str(e)}


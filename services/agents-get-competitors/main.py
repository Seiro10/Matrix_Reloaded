import asyncio
import json
import aiohttp
import urllib.parse
import os
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from utils.utils import extract_fields_from_html

load_dotenv()
BRIGHT_DATA_API_KEY = os.getenv("BRIGHTDATA_API_TOKEN")
BRD_ZONE = os.getenv("BRIGHTDATA_ZONE_ID")

test_entries = [
    {
        "URL": "https://kazhamania.com/blase-par-les-mmorpg-voici-des-alternatives/",
        "Kw name": "counters de mmo 2025",
        "Competition": "UNKNOWN",
        "People also ask": [],
        "people_also_search_for": []
    }
]


async def scrape_single_url(session: aiohttp.ClientSession, entry: dict) -> dict:
    url = entry["URL"]
    encoded_url = urllib.parse.quote_plus(url)

    payload = {
        "url": url,
        "zone": BRD_ZONE,
        "format": "raw"
    }

    headers = {
        "Authorization": f"Bearer {BRIGHT_DATA_API_KEY}",
        "Content-Type": "application/json"
    }

    async with session.post("https://api.brightdata.com/request", json=payload, headers=headers) as resp:
        if resp.status == 200:
            html = await resp.text()
            return {"html": html}
        else:
            error = await resp.text()
            return {"html": "", "error": f"BrightData API error: {resp.status} - {error}"}


async def test_scraping():
    connector = aiohttp.TCPConnector(limit=5)
    timeout = aiohttp.ClientTimeout(total=60)

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        results = []
        for entry in test_entries:
            result = await scrape_single_url(session, entry)
            html = result.get("html", "")

            if not html:
                print(f"❌ Aucun HTML récupéré pour {entry['URL']}")
                entry["error"] = result.get("error", "No HTML")
                results.append(entry)
                continue

            extracted = extract_fields_from_html(html)
            extracted.update(entry)
            results.append(extracted)

    with open("debug_result.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print("✅ Résultats sauvegardés dans debug_result.json")


if __name__ == "__main__":
    asyncio.run(test_scraping())


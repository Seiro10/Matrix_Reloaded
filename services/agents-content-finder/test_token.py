import os
import requests
from dotenv import load_dotenv

load_dotenv()

url = "https://api.dataforseo.com/v3/keywords_data/google_ads/search_volume/live"
headers = {
    "Authorization": f"Basic {os.getenv('DATAFOR_SEO_TOKEN').strip()}",
    "Content-Type": "application/json"
}
payload = [{
    "keywords": ["mmo 2025"],
    "language_code": "fr",
    "location_code": 2250,
    "date_from": "2025-03-01",
    "date_to": "2025-05-30"
}]

res = requests.post(url, headers=headers, json=payload)
print("Status:", res.status_code)
print("Body:", res.text)

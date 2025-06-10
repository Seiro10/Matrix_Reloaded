import os
import re
import requests
import openai
from bs4 import BeautifulSoup
import json
from urllib.parse import urlparse
from bs4 import Tag

SUPADATA_API_KEY = os.getenv("SUPADATA_API_KEY")
SUPADATA_HEADERS = {
    "X-API-Key": SUPADATA_API_KEY
}
SUPADATA_BASE_URL = "https://api.supadata.ai/v1"

def extract_video_id(url):
    """Extract video ID from a YouTube URL."""
    match = re.search(r"(?:v=|youtu\.be/)([a-zA-Z0-9_-]{11})", url)
    return match.group(1) if match else None


def get_video_title_supadata(video_id):
    try:
        url = f"{SUPADATA_BASE_URL}/youtube/video?id={video_id}"
        print(f"[DEBUG] GET {url}")
        res = requests.get(url, headers=SUPADATA_HEADERS, timeout=15)
        print(f"[DEBUG] Response status: {res.status_code}")
        res.raise_for_status()
        return res.json().get("title", "Unknown Title")
    except Exception as e:
        print(f"[ERROR] Failed to get title: {e}")
        return "Unknown Title"

def clean_transcription(transcript_json):
    raw_text = " ".join([item['text'] for item in transcript_json])
    clean_text = raw_text.replace(",", "")
    clean_text = " ".join(clean_text.split())
    print(clean_text)
    return clean_text

def get_transcript_supadata(video_id):
    try:
        transcript_path = f"logs/transcripts/{video_id}.txt"
        if os.path.exists(transcript_path):
            print(f"[CACHE] Transcript déjà existant → {transcript_path}")
            with open(transcript_path, "r", encoding="utf-8") as f:
                return f.read()

        # ↪ Sinon, appel API SupaData
        url = f"{SUPADATA_BASE_URL}/youtube/transcript?id={video_id}"
        print(f"[DEBUG] GET {url}")
        res = requests.get(url, headers=SUPADATA_HEADERS, timeout=15)
        print(f"[DEBUG] Response status: {res.status_code}")
        print(f"[DEBUG] Response body: {res.text}")
        res.raise_for_status()

        transcript_json = res.json().get("content", [])
        if not transcript_json:
            return None

        transcription = clean_transcription(transcript_json)
        print(f"[DEBUG] Cleaned transcription (first 100 chars): {transcription[:100]}")

        os.makedirs("logs/transcripts", exist_ok=True)
        with open(transcript_path, "w", encoding="utf-8") as f:
            f.write(transcription)
        with open(f"logs/transcripts/{video_id}_raw.json", "w", encoding="utf-8") as f:
            json.dump(transcript_json, f, indent=2, ensure_ascii=False)

        return transcription

    except Exception as e:
        print(f"[ERROR] Failed to get transcript: {e}")
        return None
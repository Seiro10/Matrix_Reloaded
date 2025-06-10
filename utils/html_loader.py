import requests

def get_article_html_from_url(url: str) -> str:
    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        return res.text
    except Exception as e:
        print(f"[ERROR] Failed to fetch article from {url}: {e}")
        return ""

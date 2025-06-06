from typing import Dict, Any, List
from core.state import State
from bs4 import BeautifulSoup
import re


def clean_single_content(scraped_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Clean the HTML content from a single scraped entry.
    """
    content = scraped_data.get("scraped_content", "")

    if not content or scraped_data.get("error"):
        return {
            **scraped_data,
            "cleaned_text": "",
            "word_count": 0
        }

    try:
        # Parse HTML
        soup = BeautifulSoup(content, 'html.parser')

        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()

        # Get text
        text = soup.get_text()

        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)

        # Remove extra spaces
        text = re.sub(r'\s+', ' ', text).strip()

        return {
            **scraped_data,
            "cleaned_text": text,
            "word_count": len(text.split()) if text else 0
        }
    except Exception as e:
        return {
            **scraped_data,
            "cleaned_text": "",
            "word_count": 0,
            "cleaning_error": str(e)
        }


def clean_all_content(state: State) -> Dict[str, Any]:
    """
    Clean all scraped content.
    """
    scraped_results = state.get("scraped_results", [])

    processed_results = []
    for scraped_data in scraped_results:
        cleaned_data = clean_single_content(scraped_data)
        processed_results.append(cleaned_data)

    return {
        "processed": processed_results
    }
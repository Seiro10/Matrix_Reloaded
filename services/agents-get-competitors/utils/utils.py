import asyncio
import json
import aiohttp
import urllib.parse
import os
from bs4 import BeautifulSoup
import re


def extract_fields_from_html(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    # Metadescription
    meta_desc = soup.find("meta", attrs={"name": "description"})
    metadesc = meta_desc.get("content", "") if meta_desc else ""

    # Titres visibles (optionnel)
    headlines = [h.get_text(strip=True) for h in soup.find_all(['h2']) if h.get_text(strip=True)]

    # Structure HTML uniquement
    structure_html = extract_structure_only(html)

    # Cleaned content brut
    cleaned = soup.get_text(separator="\n", strip=True)
    word_count = len(cleaned.split())

    return {
        "Metadescription": metadesc,
        "Headlines": headlines,
        "Structure HTML": structure_html,
        "cleaned_text": cleaned,
        "word_count": word_count,
    }


def extract_structure_only(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    # Balises qu'on considère comme éditoriales
    structural_tags = ['h1', 'h2', 'h3', 'h4', 'h5', 'p', 'ul', 'ol', 'li', 'blockquote']

    result = []

    for tag in soup.find_all(structural_tags):
        # On exclut certaines balises ou classes inutiles
        classes = tag.get("class", [])
        class_str = " ".join(classes)

        # Filtres personnalisés
        if any(skip in class_str for skip in [
            "menu", "slide", "form-", "social", "avatar", "logo", "wp-image", "comment", "lazyload"
        ]):
            continue  # on ignore cette balise

        if tag.name in ["ul", "li"] and "menu" in class_str:
            continue

        # On garde uniquement la balise et sa classe utile
        new_tag = soup.new_tag(tag.name)
        if classes:
            new_tag['class'] = classes
        result.append(str(new_tag))

    return "\n".join(result)


UNWANTED_PHRASES = [
    "Close Menu", "Submit", "Add A Comment", "Leave A Reply", "Cancel Reply",
    "Related Posts", "YouTube", "Facebook", "Twitter", "Pinterest", "Instagram",
    "X (Twitter)", "Steam", "Discord", "TikTok", "LinkedIn", "Tumblr",
    "Kazhamania", "Save my name", "ThemeSphere", "Designed by", "©", "Press Enter"
]

def clean_html_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    # Remove <script>, <style>, <footer>, navs, etc.
    for tag in soup(["script", "style", "footer", "nav", "form", "header", "noscript", "aside"]):
        tag.decompose()

    # Extract text and normalize whitespace
    text = soup.get_text(separator="\n")
    text = re.sub(r"\n+", "\n", text)          # Remove multiple line breaks
    text = re.sub(r"[ \t]+", " ", text)        # Normalize spaces
    text = text.strip()

    # Remove unwanted phrases
    lines = text.split("\n")
    filtered = [line.strip() for line in lines if not any(phrase.lower() in line.lower() for phrase in UNWANTED_PHRASES)]

    return "\n".join(filtered)


import os
import re
import requests
import openai
from bs4 import BeautifulSoup
import json
from urllib.parse import urlparse
from bs4 import Tag
from utils.transcript import get_transcript_supadata


def extract_html_blocks(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')

    if not soup.body:
        print("[DEBUG] Pas de <body> trouvé dans le HTML")
    else:
        print("[DEBUG] <body> trouvé ✅")
    blocks = []
    current_block = []
    current_title = None

    content_tags = [
        'p', 'ul', 'ol', 'img', 'figure', 'blockquote',
        'div', 'section', 'a', 'strong', 'em', 'mark', 'iframe'
    ]
    keep_classes = [
        'wp-block-quote',
        'cg-box-layout-eleven',
        'wp-block-shortcode'
    ]

    soup = BeautifulSoup(html_content, 'html.parser')
    content_root = soup.find('article') or soup

    for elem in content_root.descendants:
        if not getattr(elem, 'name', None):
            continue

        # Titres : on découpe
        if elem.name in ['h1', 'h2', 'h3']:
            if current_block:
                blocks.append({'title': current_title, 'content': current_block})
                current_block = []
            current_title = elem

        # Contenu riche
        elif elem.name in content_tags:
            # Garde les div/section spécifiques (affiliate, shortcode, citation, etc.)
            cls = elem.get('class', [])
            if isinstance(cls, str):
                cls = [cls]
            if any(c for c in cls if c in keep_classes):
                current_block.append(elem)

            # Contenu classique
            elif elem.name in ['p', 'ul', 'ol', 'img', 'blockquote', 'figure']:
                current_block.append(elem)

    if current_block:
        blocks.append({'title': current_title, 'content': current_block})

    print(f"[DEBUG] {len(blocks)} blocs extraits (avec blocs spéciaux)")
    return blocks


def reconstruct_blocks(blocks):
    html = ""
    for block in blocks:
        if block['title']:
            html += str(block['title']) + "\n"
        for elem in block['content']:
            html += str(elem) + "\n"
    return html

def strip_duplicate_title_and_featured_image(html):
    soup = BeautifulSoup(html, 'html.parser')

    # Supprimer H1
    h1 = soup.find('h1')
    if h1:
        print("[CLEAN] 🔠 H1 supprimé :", h1.text.strip()[:60])
        h1.decompose()

    # Supprimer img principale (souvent wp-post-image)
    main_img = soup.find('img', class_="wp-post-image")
    if main_img:
        print("[CLEAN] 🖼️ Image principale supprimée")
        main_img.decompose()

    return str(soup)

def update_and_reconstruct_article(filepath, subject, transcript_text):
    html = load_html_file(filepath)
    blocks = extract_html_blocks(html)
    updated_blocks = []

    for block in blocks:
        print(f"[DEBUG] Traitement du bloc : {block['title'].get_text() if block['title'] else 'Sans titre'}")
        updated_block = update_block_if_needed(block, subject, transcript_text)
        updated_blocks.append(updated_block)

    return reconstruct_blocks(updated_blocks)
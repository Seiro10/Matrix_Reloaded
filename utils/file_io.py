import os
import re
import requests
import openai
from bs4 import BeautifulSoup
import json
from urllib.parse import urlparse
from bs4 import Tag
import os

def write_to_txt(content, output_path="./updated_article.txt"):
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)


def save_log(name: str, data: str, log_dir="logs/memory_pipeline"):
    os.makedirs(log_dir, exist_ok=True)
    with open(f"{log_dir}/{name}.txt", "w", encoding="utf-8") as f:
        f.write(data)


def load_html_file(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()

def log_debug(msg: str):
    print(f"[DEBUG] {msg}")


def save_html_to_file(html: str, filename: str, directory: str = "logs/cleaned") -> None:
    os.makedirs(directory, exist_ok=True)
    filepath = os.path.join(directory, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[FILE_IO] 💾 HTML nettoyé sauvegardé dans {filepath}")

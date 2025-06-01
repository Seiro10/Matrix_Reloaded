import os
import json

PROMPT_TEMPLATE_MAP = {
    "News": "prompts/news_fr.json",
    "Guide": "prompts/guide_fr.json",
    "Comparison": "prompts/comparison_fr.json",
    "Ranking": "prompts/ranking_fr.json",
    "Critics": "prompts/critics_fr.json",
    "Affiliate": "prompts/affiliate_fr.json"
}


def load_prompt_template(article_type: str) -> dict:
    template_path = PROMPT_TEMPLATE_MAP.get(article_type)
    if not template_path or not os.path.exists(template_path):
        raise FileNotFoundError(f"Missing prompt template for article type: {article_type}")
    with open(template_path, "r", encoding="utf-8") as f:
        return json.load(f)

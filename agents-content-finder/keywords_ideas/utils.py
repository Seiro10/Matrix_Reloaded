import os
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import random

def load_google_ads_client():
    config = {
        "developer_token": os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN"),
        "client_id": os.getenv("GOOGLE_ADS_CLIENT_ID"),
        "client_secret": os.getenv("GOOGLE_ADS_CLIENT_SECRET"),
        "refresh_token": os.getenv("GOOGLE_ADS_REFRESH_TOKEN"),
        "login_customer_id": os.getenv("GOOGLE_ADS_LOGIN_CUSTOMER_ID"),
        "use_proto_plus": True,
        "token_uri": "https://oauth2.googleapis.com/token",
    }
    return GoogleAdsClient.load_from_dict(config)


def get_keyword_ideas(client, seed_keyword: str, customer_id: str) -> list:
    if os.getenv("USE_MOCK_KEYWORDS", "false").lower() == "true":
        print(f"[MOCK] Returning fake keyword data for: {seed_keyword}")
        return generate_fake_keywords(seed_keyword)

    # Real API logic
    service = client.get_service("KeywordPlanIdeaService")

    keyword_seed = client.get_type("KeywordSeed")
    keyword_seed.keywords.append(seed_keyword)

    geo_target = client.get_type("LocationInfo")
    geo_target.geo_target_constant = "geoTargetConstants/2840"  # 🇺🇸 United States

    request = client.get_type("GenerateKeywordIdeasRequest")
    request.customer_id = customer_id
    request.language = "languageConstants/1000"  # English
    request.geo_target_constants.append(geo_target.geo_target_constant)
    request.keyword_seed.keywords.append(seed_keyword)

    results = service.generate_keyword_ideas(request=request)

    output = []
    for idea in results:
        text = idea.text
        volume = idea.keyword_idea_metrics.avg_monthly_searches
        competition_value = idea.keyword_idea_metrics.competition.value
        competition = float(competition_value) / 2.0  # LOW = 0.0, MEDIUM = 0.5, HIGH = 1.0

        output.append({
            "keyword": text,
            "monthly_searches": volume,
            "competition": "LOW" if competition < 0.3 else "MEDIUM"
        })

    return sorted(output, key=lambda x: x["monthly_searches"], reverse=True)[:50]


def generate_fake_keywords(seed: str) -> list:
    base = [
        f"{seed} guide",
        f"{seed} 2025",
        f"{seed} stratégie",
        f"meilleurs builds {seed}",
        f"{seed} ranked tips",
        f"jouer {seed} efficacement",
        f"counters de {seed}",
        f"{seed} débutant"
    ]

    return [
        {
            "keyword": kw,
            "monthly_searches": random.randint(100, 5000),
            "competition": "LOW" if i % 2 == 0 else "MEDIUM"
        }
        for i, kw in enumerate(base)
    ]

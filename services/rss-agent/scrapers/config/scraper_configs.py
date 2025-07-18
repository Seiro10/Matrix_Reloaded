"""Enhanced scraper configuration with banner image support"""

from typing import Dict, List, Optional

class ScraperConfig:
    def __init__(self,
                 url: str,
                 website_name: str,
                 theme: str,
                 max_articles: int = 5,
                 banner_selectors: List[str] = None,
                 article_selectors: List[str] = None):
        self.url = url
        self.website_name = website_name
        self.theme = theme
        self.max_articles = max_articles
        self.banner_selectors = banner_selectors or []
        self.article_selectors = article_selectors or []

# Enhanced Riot Games configurations with stable selectors
RIOT_SCRAPER_CONFIGS = {
    "league_of_legends": ScraperConfig(
        url="https://www.leagueoflegends.com/fr-fr/news/",
        website_name="League of Legends",
        theme="Gaming",
        max_articles=5,
        banner_selectors=[
            # Primary: data-testid selectors
            'img[data-testid="banner-image"]',
            'img[data-testid="hero-image"]',
            'img[data-testid="featured-image"]',
            # Fallback: content-based selectors
            'img[src*="cmsassets.rgpub.io"]',
            'img[src*="1920x1080"]',
            'img[src*="1200x"]',
        ],
        article_selectors=[
            # Primary: data-testid selectors for articles
            'a[data-testid*="article"]',
            'a[data-testid*="news"]',
            'a[data-testid*="post"]',
            # Fallback: href-based selectors
            'a[href*="/news/"]',
            'a[href*="/fr-fr/news/"]'
        ]
    ),
    "valorant": ScraperConfig(
        url="https://playvalorant.com/fr-fr/news/",
        website_name="Valorant",
        theme="Gaming",
        max_articles=3,
        banner_selectors=[
            # Primary: data-testid selectors
            'img[data-testid="banner-image"]',
            'img[data-testid="hero-image"]',
            'img[data-testid="featured-image"]',
            # Fallback: content-based selectors
            'img[src*="cmsassets.rgpub.io"]',
            'img[src*="1920x1080"]',
            'img[src*="1200x"]',
        ],
        article_selectors=[
            # Primary: data-testid selectors for articles
            'a[data-testid*="article"]',
            'a[data-testid*="news"]',
            'a[data-testid*="post"]',
            # Fallback: href-based selectors
            'a[href*="/news/"]',
            'a[href*="/fr-fr/news/"]'
        ]
    ),
    "teamfight_tactics": ScraperConfig(
        url="https://teamfighttactics.leagueoflegends.com/fr-fr/news/",
        website_name="TFT",
        theme="Gaming",
        max_articles=3,
        banner_selectors=[
            # Primary: data-testid selectors
            'img[data-testid="banner-image"]',
            'img[data-testid="hero-image"]',
            'img[data-testid="featured-image"]',
            # Fallback: content-based selectors
            'img[src*="cmsassets.rgpub.io"]',
            'img[src*="1920x1080"]',
            'img[src*="1200x"]',
        ],
        article_selectors=[
            # Primary: data-testid selectors for articles
            'a[data-testid*="article"]',
            'a[data-testid*="news"]',
            'a[data-testid*="post"]',
            # Fallback: href-based selectors
            'a[href*="/news/"]',
            'a[href*="/fr-fr/news/"]'
        ]
    ),
    "wild_rift": ScraperConfig(
        url="https://wildrift.leagueoflegends.com/fr-fr/news/",
        website_name="Wild Rift",
        theme="Gaming",
        max_articles=3,
        banner_selectors=[
            # Primary: data-testid selectors
            'img[data-testid="banner-image"]',
            'img[data-testid="hero-image"]',
            'img[data-testid="featured-image"]',
            # Fallback: content-based selectors
            'img[src*="cmsassets.rgpub.io"]',
            'img[src*="1920x1080"]',
            'img[src*="1200x"]',
        ],
        article_selectors=[
            # Primary: data-testid selectors for articles
            'a[data-testid*="article"]',
            'a[data-testid*="news"]',
            'a[data-testid*="post"]',
            # Fallback: href-based selectors
            'a[href*="/news/"]',
            'a[href*="/fr-fr/news/"]'
        ]
    ),
    "legends_of_runeterra": ScraperConfig(
        url="https://playruneterra.com/fr-fr/news",
        website_name="Legends of Runeterra",
        theme="Gaming",
        max_articles=3,
        banner_selectors=[
            # Primary: data-testid selectors
            'img[data-testid="banner-image"]',
            'img[data-testid="hero-image"]',
            'img[data-testid="featured-image"]',
            # Fallback: content-based selectors
            'img[src*="cmsassets.rgpub.io"]',
            'img[src*="1920x1080"]',
            'img[src*="1200x"]',
        ],
        article_selectors=[
            # Primary: data-testid selectors for articles
            'a[data-testid*="article"]',
            'a[data-testid*="news"]',
            'a[data-testid*="post"]',
            # Fallback: href-based selectors
            'a[href*="/news/"]',
            'a[href*="/fr-fr/news/"]'
        ]
    )
}

def get_scraper_config(scraper_key: str) -> Optional[ScraperConfig]:
    """Get configuration for a specific scraper"""
    return RIOT_SCRAPER_CONFIGS.get(scraper_key)

def get_all_scraper_keys() -> List[str]:
    """Get all available scraper keys"""
    return list(RIOT_SCRAPER_CONFIGS.keys())

# Legacy compatibility functions (for backward compatibility)
def get_riot_site_config(site_key: str):
    """Get configuration for a specific Riot site (legacy compatibility)"""
    config = get_scraper_config(site_key)
    if config:
        return {
            "url": config.url,
            "website_name": config.website_name,
            "theme": config.theme,
            "max_articles": config.max_articles
        }
    return None

def get_all_riot_sites():
    """Get all available Riot sites (legacy compatibility)"""
    return get_all_scraper_keys()
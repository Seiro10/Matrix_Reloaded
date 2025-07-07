"""Configuration for all Riot Games websites"""

RIOT_SITES_CONFIG = {
    "valorant": {
        "url": "https://playvalorant.com/fr-fr/news/",
        "website_name": "Valorant",
        "theme": "Gaming",
        "max_articles": 3
    },
    "teamfight_tactics": {
        "url": "https://teamfighttactics.leagueoflegends.com/fr-fr/news/",
        "website_name": "TFT",
        "theme": "Gaming",
        "max_articles": 3
    },
    "wild_rift": {
        "url": "https://wildrift.leagueoflegends.com/fr-fr/news/",
        "website_name": "Wild Rift",
        "theme": "Gaming",
        "max_articles": 3
    },
    "legends_of_runeterra": {
        "url": "https://playruneterra.com/fr-fr/news",
        "website_name": "Legends of Runeterra",  # ✅ Fixed
        "theme": "Gaming",
        "max_articles": 3
    }
}

def get_riot_site_config(site_key: str):
    """Get configuration for a specific Riot site"""
    return RIOT_SITES_CONFIG.get(site_key)

def get_all_riot_sites():
    """Get all available Riot sites"""
    return list(RIOT_SITES_CONFIG.keys())
# File: services/content-router-agent/src/config.py

from dataclasses import dataclass
from typing import List
import os


@dataclass
class WebsiteConfig:
    site_id: int
    name: str
    domain: str
    niche: str
    theme: str
    language: str
    sitemap_url: str
    wordpress_api_url: str


# Your 5 WordPress sites configuration
WEBSITES = [
    WebsiteConfig(
        site_id=1,
        name="Gaming Hub",
        domain="gaminghub.fr",
        niche="gaming",
        theme="Gaming hardware, reviews, guides",
        language="FR",
        sitemap_url="https://gaminghub.fr/sitemap.xml",
        wordpress_api_url="https://gaminghub.fr/wp-json/wp/v2/"
    ),
    WebsiteConfig(
        site_id=2,
        name="Motivation Plus",
        domain="motivationplus.fr",
        niche="motivation",
        theme="Personal development, productivity, mindset",
        language="FR",
        sitemap_url="https://motivationplus.fr/sitemap.xml",
        wordpress_api_url="https://motivationplus.fr/wp-json/wp/v2/"
    )
]


# Environment Configuration
class Settings:
    def __init__(self):
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.project_id = os.getenv("PROJECT_ID")
        self.environment = os.getenv("ENVIRONMENT", "development")
        self.db_path = os.getenv("DB_PATH", "/app/data/content_db.sqlite")
        self.port = int(os.getenv("PORT", 8080))

        # Validation
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def is_development(self) -> bool:
        return self.environment.lower() == "development"


# Global settings instance
settings = Settings()
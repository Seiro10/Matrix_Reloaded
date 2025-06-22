# File: services/router-agent/src/config.py

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


WEBSITES = [
    WebsiteConfig(
        site_id=1,
        name="Stuffgaming",
        domain="stuffgaming.fr",
        niche="gaming",
        theme="Gaming hardware, reviews, guides",
        language="FR",
        sitemap_url="https://stuffgaming.fr/sitemap.xml",
        wordpress_api_url="http://stuffgaming.fr/wp-json/wp/v2/"
    ),
    WebsiteConfig(
        site_id=2,
        name="Motivation Plus",
        domain="motivationplus.fr",
        niche="motivation",
        theme="Personal development, productivity, mindset",
        language="FR",
        sitemap_url="http://example.com/sitemap.xml",
        wordpress_api_url="http://example.com/wp-json/wp/v2/"
    )
]


class Settings:
    def __init__(self):
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")  # Added for Claude
        self.project_id = os.getenv("PROJECT_ID")
        self.environment = os.getenv("ENVIRONMENT", "development")
        # Fix the database path
        self.db_path = os.getenv("DB_PATH", "./data/content_db.sqlite")
        self.port = int(os.getenv("PORT", 8080))

        # UPDATED: Service URLs for rewriter-main
        self.rewriter_agent_url = os.getenv("REWRITER_AGENT_URL", "http://localhost:8085")  # Changed to 8085
        self.metadata_generator_url = os.getenv("METADATA_GENERATOR_URL", "http://localhost:8084")

        # Validation
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        if not self.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required")

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def is_development(self) -> bool:
        return self.environment.lower() == "development"


# Global settings instance
settings = Settings()
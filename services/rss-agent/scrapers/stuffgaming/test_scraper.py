from typing import List
from datetime import datetime
from scrapers.base_scraper import BaseScraper
from models.schemas import NewsItem
import logging

logger = logging.getLogger(__name__)


class TestScraper(BaseScraper):
    def __init__(self):
        super().__init__(
            base_url="https://example.com",
            website_name="Test Gaming Site",
            theme="Gaming"
        )

    def scrape_news(self) -> List[NewsItem]:
        """Create test news items to verify the pipeline"""
        logger.info(f"[DEBUG] Creating test news items for {self.website_name}")

        news_items = [
            NewsItem(
                title="Test Gaming News: New Champions Released",
                content="This is a test article about new champions being released in the game. The article contains detailed information about their abilities and gameplay mechanics.",
                images=[
                    "https://picsum.photos/400/300?random=1",
                    "https://picsum.photos/400/300?random=2"
                ],
                website=self.website_name,
                destination_website="Test Gaming Site",
                theme=self.theme,
                url="https://example.com/news/new-champions",
                published_date=datetime.now()
            ),
            NewsItem(
                title="Test Gaming News: Major Game Update",
                content="A major update has been released with new features, bug fixes, and balance changes. Players can expect improved performance and new gameplay options.",
                images=[
                    "https://picsum.photos/400/300?random=3"
                ],
                website=self.website_name,
                destination_website="Test Gaming Site",
                theme=self.theme,
                url="https://example.com/news/major-update",
                published_date=datetime.now()
            )
        ]

        logger.info(f"[DEBUG] Created {len(news_items)} test news items")
        return news_items
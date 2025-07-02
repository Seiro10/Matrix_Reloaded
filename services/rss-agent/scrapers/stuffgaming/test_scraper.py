from typing import List
from datetime import datetime
from scrapers.base_scraper import BaseScraper
from models.schemas import NewsItem
from models.tracking import ScrapingTracker
import logging

logger = logging.getLogger(__name__)


class TestScraper(BaseScraper):
    def __init__(self):
        super().__init__(
            base_url="https://example.com",
            website_name="Test Gaming Site",
            theme="Gaming"
        )
        # ✅ Ajouter le tracker
        self.tracker = ScrapingTracker()

    def scrape_news(self) -> List[NewsItem]:
        """Create test news items to verify the pipeline - only new ones"""
        logger.info(f"[DEBUG] Creating test news items for {self.website_name}")

        # Create different articles based on current time to simulate new content
        current_hour = datetime.now().hour
        current_minute = datetime.now().minute

        all_news_items = [
            NewsItem(
                title=f"Test Gaming News: New Update {current_hour}:{current_minute:02d}",
                content=f"This is a test article about a new update released at {current_hour}:{current_minute:02d}. The article contains detailed information about new features and improvements.",
                images=[
                    "https://picsum.photos/400/300?random=1",
                    "https://picsum.photos/400/300?random=2"
                ],
                website=self.website_name,
                destination_website="Stuffgaming",
                theme=self.theme,
                url=f"https://example.com/news/update-{current_hour}-{current_minute}",
                published_date=datetime.now()
            ),
            NewsItem(
                title=f"Test Gaming News: Event Announcement {current_hour}",
                content=f"A special event has been announced for hour {current_hour}. Players can expect new challenges and rewards during this limited-time event.",
                images=[
                    "https://picsum.photos/400/300?random=3"
                ],
                website=self.website_name,
                destination_website="Stuffgaming",
                theme=self.theme,
                url=f"https://example.com/news/event-{current_hour}",
                published_date=datetime.now()
            )
        ]

        # ✅ Filter for new articles only
        articles_data = [item.model_dump() for item in all_news_items]
        new_articles_data = self.tracker.filter_new_articles("test_scraper", articles_data)

        logger.info(f"[DEBUG] New test articles: {len(new_articles_data)} out of {len(articles_data)}")

        # Convert back to NewsItem objects
        new_news_items = [NewsItem(**article_data) for article_data in new_articles_data]

        # ✅ Mark articles as seen
        if articles_data:
            self.tracker.mark_articles_as_seen("test_scraper", articles_data)
            logger.info(f"[DEBUG] Marked {len(articles_data)} test articles as seen")

        return new_news_items
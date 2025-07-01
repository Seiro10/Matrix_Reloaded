from typing import List, Optional
from models.schemas import NewsItem, CopywriterPayload
from services.s3_service import S3Service
import logging

logger = logging.getLogger(__name__)


class ContentProcessor:
    def __init__(self):
        self.s3_service = S3Service()

    async def process_news_item(self, news_item: NewsItem) -> Optional[CopywriterPayload]:
        """Process a news item and prepare payload for copywriter"""
        logger.info(f"[DEBUG] Processing news item: {news_item.title}")

        # Upload images to S3 (called from Celery task, so S3 URLs should already be provided)
        # This method is mainly for creating the payload now
        payload = CopywriterPayload(
            title=news_item.title,
            content=news_item.content,
            images=news_item.images,
            website=news_item.website,
            destination_website=news_item.destination_website,
            theme=news_item.theme,
            url=news_item.url,
            s3_image_urls=[]  # Will be populated by the Celery task
        )

        logger.info(f"[DEBUG] Prepared payload for copywriter:")
        logger.info(f"[DEBUG] - Title: {payload.title}")
        logger.info(f"[DEBUG] - Content length: {len(payload.content)}")
        logger.info(f"[DEBUG] - Original images: {len(payload.images)}")
        logger.info(f"[DEBUG] - Website: {payload.website}")
        logger.info(f"[DEBUG] - Destination: {payload.destination_website}")
        logger.info(f"[DEBUG] - Theme: {payload.theme}")

        return payload

    def _should_skip_article(self, news_item: NewsItem) -> bool:
        """Check if article should be skipped"""
        # Skip if content is just "Article from [category]"
        if news_item.content.startswith("Article from"):
            return True

        # Skip if URL is a video (YouTube, Vimeo, etc.)
        video_domains = ['youtube.com', 'youtu.be', 'vimeo.com', 'twitch.tv']
        if any(domain in news_item.url.lower() for domain in video_domains):
            return True

        # Skip if content is too short (less than 50 characters)
        if len(news_item.content.strip()) < 50:
            return True

        # Skip if title contains video indicators
        video_keywords = ['vidéo', 'video', 'bande-annonce', 'trailer', 'musique', 'music']
        if any(keyword in news_item.title.lower() for keyword in video_keywords):
            return True

        return False

    def _get_skip_reason(self, news_item: NewsItem) -> str:
        """Get reason why article was skipped"""
        if news_item.content.startswith("Article from"):
            return "Generic content placeholder"

        video_domains = ['youtube.com', 'youtu.be', 'vimeo.com', 'twitch.tv']
        if any(domain in news_item.url.lower() for domain in video_domains):
            return "Video URL detected"

        if len(news_item.content.strip()) < 50:
            return "Content too short"

        video_keywords = ['vidéo', 'video', 'bande-annonce', 'trailer', 'musique', 'music']
        if any(keyword in news_item.title.lower() for keyword in video_keywords):
            return "Video content in title"

        return "Unknown reason"

    def send_to_copywriter(self, payload: CopywriterPayload):
        """Send payload to copywriter (for now just print)"""
        if payload is None:
            logger.info("[DEBUG] === ARTICLE SKIPPED - NOT SENDING TO COPYWRITER ===")
            return

        logger.info("[DEBUG] === SENDING TO COPYWRITER ===")
        logger.info(f"[DEBUG] PAYLOAD: {payload.model_dump_json(indent=2)}")
        logger.info("[DEBUG] === END COPYWRITER PAYLOAD ===")
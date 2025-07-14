from typing import List, Optional
from models.schemas import NewsItem, CopywriterPayload
from services.s3_service import S3Service
import requests  # Add this import at the top
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
            s3_image_urls=[]
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
        """Send payload to router agent for processing"""
        if payload is None:
            logger.info("[DEBUG] === ARTICLE SKIPPED - NOT SENDING TO ROUTER ===")
            return

        try:
            from config.settings import settings

            # Get router agent URL from settings
            router_url = getattr(settings, 'router_agent_url', 'http://localhost:8080')

            # Transform CopywriterPayload to RSSPayload format expected by router
            rss_payload = {
                "title": payload.title,
                "content": payload.content,
                "images": payload.images,
                "website": payload.website,
                "destination_website": payload.destination_website,
                "theme": payload.theme,
                "url": payload.url,
                "s3_image_urls": payload.s3_image_urls,
                "main_image": payload.s3_image_urls[0] if payload.s3_image_urls else (
                    payload.images[0] if payload.images else ""),
                "banner_image": payload.banner_image,
                "post_type": "News",
                "original_post_url": payload.original_post_url
            }

            logger.info("[DEBUG] === SENDING TO ROUTER AGENT ===")
            logger.info(f"[DEBUG] Router URL: {router_url}/rss-route")
            logger.info(f"[DEBUG] Payload title: {payload.title}")
            logger.info(f"[DEBUG] Destination: {payload.destination_website}")

            # Send to router agent
            response = requests.post(
                f"{router_url}/rss-route",
                json=rss_payload,
                headers={"Content-Type": "application/json"},
                timeout=120  # 2 minute timeout
            )

            if response.status_code == 200:
                result = response.json()
                logger.info("[DEBUG] ✅ Successfully sent to router agent")
                logger.info(f"[DEBUG] Router response: {result.get('success', False)}")
                if result.get('agent_response'):
                    logger.info(
                        f"[DEBUG] Metadata generator status: {result['agent_response'].get('success', 'unknown')}")
            else:
                logger.error(f"[DEBUG] ❌ Router agent returned error: {response.status_code}")
                logger.error(f"[DEBUG] Response: {response.text}")

        except requests.exceptions.Timeout:
            logger.error("[DEBUG] ❌ Timeout sending to router agent")
        except requests.exceptions.ConnectionError:
            logger.error(f"[DEBUG] ❌ Cannot connect to router agent at {router_url}")
        except Exception as e:
            logger.error(f"[DEBUG] ❌ Error sending to router agent: {e}")

        logger.info("[DEBUG] === END ROUTER AGENT COMMUNICATION ===")
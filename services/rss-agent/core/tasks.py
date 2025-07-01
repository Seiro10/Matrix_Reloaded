from celery import Celery
from config.settings import settings
from models.schemas import NewsItem, CopywriterPayload
import asyncio
import logging
from typing import List
import json

logger = logging.getLogger(__name__)

celery_app = Celery(
    "rss_agent",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend
)


@celery_app.task(bind=True, max_retries=3)
def scrape_website(self, scraper_name: str):
    """Celery task to scrape a website"""
    try:
        logger.info(f"[DEBUG] Starting scraping task for {scraper_name}")

        # Import here to avoid circular imports
        from scrapers.stuffgaming.league_of_legends import LeagueOfLegendsScraper
        from scrapers.stuffgaming.test_scraper import TestScraper

        scrapers = {
            'league_of_legends': LeagueOfLegendsScraper(),
            'test_scraper': TestScraper()
        }

        if scraper_name not in scrapers:
            raise ValueError(f"Unknown scraper: {scraper_name}")

        scraper = scrapers[scraper_name]
        news_items = scraper.scrape_news()

        # Convert to dict for JSON serialization
        news_items_data = [item.model_dump() for item in news_items]

        logger.info(f"[DEBUG] Scraping completed for {scraper_name}: {len(news_items_data)} items")

        # Queue processing jobs for each news item
        for item_data in news_items_data:
            process_news_item.apply_async(args=[item_data], queue='processing')

        return {
            "scraper": scraper_name,
            "items_found": len(news_items_data),
            "status": "completed"
        }

    except Exception as exc:
        logger.error(f"[DEBUG] Scraping task failed for {scraper_name}: {exc}")
        if self.request.retries < self.max_retries:
            logger.info(f"[DEBUG] Retrying in 60 seconds... (attempt {self.request.retries + 1})")
            raise self.retry(countdown=60)
        raise


@celery_app.task(bind=True, max_retries=3)
def process_news_item(self, news_item_data: dict):
    """Celery task to process a news item"""
    try:
        logger.info(f"[DEBUG] Processing news item: {news_item_data.get('title', 'Unknown')}")

        # Convert back to NewsItem
        news_item = NewsItem(**news_item_data)

        # Import content processor
        from services.content_processor import ContentProcessor
        content_processor = ContentProcessor()

        # Check if we should skip this article first (synchronous check)
        if content_processor._should_skip_article(news_item):
            logger.info(
                f"[DEBUG] Skipping article: {news_item.title} - Reason: {content_processor._get_skip_reason(news_item)}")
            return {
                "title": news_item.title,
                "s3_images_uploaded": 0,
                "status": "skipped",
                "sent_to_copywriter": False,
                "skip_reason": content_processor._get_skip_reason(news_item)
            }

        # Process images in parallel
        image_upload_jobs = []
        for i, image_url in enumerate(news_item.images):
            s3_key = f"{news_item.website.lower().replace(' ', '_')}/{news_item.title[:30]}_{i}.jpg"
            job = upload_image.apply_async(args=[image_url, s3_key], queue='uploads')
            image_upload_jobs.append(job)

        # Wait for all image uploads to complete
        s3_image_urls = []
        for job in image_upload_jobs:
            try:
                result = job.get(timeout=30)  # 30 second timeout per image
                if result.get('success') and result.get('s3_url'):
                    s3_image_urls.append(result['s3_url'])
            except Exception as e:
                logger.error(f"[DEBUG] Image upload job failed: {e}")

        # Create payload using async function in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            payload = loop.run_until_complete(content_processor.process_news_item(news_item))
        finally:
            loop.close()

        # Send to copywriter
        if payload:
            content_processor.send_to_copywriter(payload)
            return {
                "title": news_item.title,
                "s3_images_uploaded": len(s3_image_urls),
                "status": "completed",
                "sent_to_copywriter": True
            }
        else:
            return {
                "title": news_item.title,
                "s3_images_uploaded": len(s3_image_urls),
                "status": "skipped",
                "sent_to_copywriter": False
            }

    except Exception as exc:
        logger.error(f"[DEBUG] Processing task failed: {exc}")
        if self.request.retries < self.max_retries:
            logger.info(f"[DEBUG] Retrying in 30 seconds... (attempt {self.request.retries + 1})")
            raise self.retry(countdown=30)
        raise


@celery_app.task(bind=True, max_retries=3)
def upload_image(self, image_url: str, s3_key: str):
    """Celery task to upload an image to S3"""
    try:
        from services.s3_service import S3Service

        logger.info(f"[DEBUG] Uploading image: {image_url}")

        s3_service = S3Service()

        # Run async function in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            s3_url = loop.run_until_complete(s3_service.upload_image_from_url(image_url, s3_key))
        finally:
            loop.close()

        if s3_url:
            logger.info(f"[DEBUG] Image uploaded successfully: {s3_url}")
            return {"success": True, "s3_url": s3_url}
        else:
            raise Exception("Upload failed")

    except Exception as exc:
        logger.error(f"[DEBUG] Image upload task failed: {exc}")
        if self.request.retries < self.max_retries:
            logger.info(f"[DEBUG] Retrying image upload in 10 seconds... (attempt {self.request.retries + 1})")
            raise self.retry(countdown=10)
        return {"success": False, "error": str(exc)}
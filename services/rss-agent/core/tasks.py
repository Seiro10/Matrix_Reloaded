from celery import Celery
from config.settings import settings
import asyncio
import logging
from typing import List
import json
import os
from dotenv import load_dotenv

# Model imports
from models.schemas import NewsItem, CopywriterPayload
from models.tracking import ScrapingTracker

# Service imports
from services.content_processor import ContentProcessor
from services.s3_service import S3Service

# Load .env for Celery workers
load_dotenv()

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
        from scrapers.stuffgaming.riot_games_scraper import RiotGamesScraper
        from scrapers.config.riot_sites import get_all_riot_sites

        scrapers = {
            'league_of_legends': LeagueOfLegendsScraper(),
            'test_scraper': TestScraper()
        }

        # Add all Riot Games scrapers dynamically
        for site_key in get_all_riot_sites():
            scrapers[site_key] = RiotGamesScraper(site_key)

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

        # Check if we should skip this article first
        if content_processor._should_skip_article(news_item):
            skip_reason = content_processor._get_skip_reason(news_item)
            logger.info(f"[DEBUG] Skipping article: {news_item.title} - Reason: {skip_reason}")

            # ✅ Mark skipped article as seen so it won't be processed again
            from models.tracking import ScrapingTracker
            tracker = ScrapingTracker()
            # Determine scraper name from website
            scraper_name = news_item.website.lower().replace(' ', '_')
            if scraper_name == "valorant":
                scraper_name = "valorant"
            elif scraper_name == "tft":
                scraper_name = "teamfight_tactics"
            # Add other mappings as needed

            tracker.mark_articles_as_seen(scraper_name, [news_item_data])

            return {
                "title": news_item.title,
                "s3_images_uploaded": 0,
                "status": "skipped",
                "sent_to_copywriter": False,
                "skip_reason": skip_reason
            }

        # Queue image uploads but don't wait for them
        image_upload_jobs = []
        for i, image_url in enumerate(news_item.images):
            s3_key = f"{news_item.website.lower().replace(' ', '_')}/{news_item.title[:30]}_{i}.jpg"
            job = upload_image.apply_async(args=[image_url, s3_key], queue='uploads')
            image_upload_jobs.append(job)

        # Create simple payload without async processing
        payload = CopywriterPayload(
            title=news_item.title,
            content=news_item.content,
            images=news_item.images,
            website=news_item.website,
            destination_website=news_item.destination_website,
            theme=news_item.theme,
            url=news_item.url,
            s3_image_urls=[]  # Empty for now, images upload in background
        )

        # Send to copywriter
        content_processor.send_to_copywriter(payload)

        # ✅ Mark article as seen ONLY after successful processing
        from models.tracking import ScrapingTracker
        tracker = ScrapingTracker()
        # Determine scraper name from website
        scraper_name = news_item.website.lower().replace(' ', '_')
        if scraper_name == "valorant":
            scraper_name = "valorant"
        elif scraper_name == "tft":
            scraper_name = "teamfight_tactics"
        # Add other mappings as needed

        tracker.mark_articles_as_seen(scraper_name, [news_item_data])

        logger.info(f"[DEBUG] Successfully processed and sent article: {news_item.title}")

        return {
            "title": news_item.title,
            "s3_images_uploaded": len(image_upload_jobs),
            "status": "completed",
            "sent_to_copywriter": True,
            "image_jobs_queued": len(image_upload_jobs)
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

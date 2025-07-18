from celery import Celery
from config.settings import settings
import asyncio
import logging
from typing import List, Optional
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


# Move the helper function outside the task, at module level
def _get_scraper_name(website: str) -> str:
    """Helper function to get scraper name from website name"""
    scraper_name = website.lower().replace(' ', '_')
    if scraper_name == "valorant":
        return "valorant"
    elif scraper_name == "tft":
        return "teamfight_tactics"
    elif scraper_name == "league_of_legends":
        return "league_of_legends"
    elif scraper_name == "wild_rift":
        return "wild_rift"
    elif scraper_name == "legends_of_runeterra":
        return "legends_of_runeterra"
    return scraper_name


@celery_app.task(bind=True, max_retries=3)
def scrape_website(self, scraper_name: str):
    """Celery task to scrape a website using unified scraper"""
    try:
        logger.info(f"[DEBUG] Starting scraping task for {scraper_name}")

        # Import scrapers
        from scrapers.stuffgaming.unified_riot_scraper import UnifiedRiotScraper
        from scrapers.stuffgaming.test_scraper import TestScraper
        from scrapers.stuffgaming.blizzard_news_scraper import BlizzardNewsScraper

        # Choose appropriate scraper
        if scraper_name == "blizzard_news":
            scraper = BlizzardNewsScraper()
        elif scraper_name == "test_scraper":
            scraper = TestScraper()
        else:
            scraper = UnifiedRiotScraper(scraper_name)

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
        logger.error(f"[DEBUG] Exception details: {type(exc).__name__}: {str(exc)}")
        if self.request.retries < self.max_retries:
            logger.info(f"[DEBUG] Retrying in 60 seconds... (attempt {self.request.retries + 1})")
            raise self.retry(countdown=60)
        raise


@celery_app.task(bind=True, max_retries=3)
def process_news_item(self, news_item_data: dict):
    """Celery task to process a news item with banner image priority"""
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

            # Mark skipped article as seen
            from models.tracking import ScrapingTracker
            tracker = ScrapingTracker()
            scraper_name = _get_scraper_name(news_item.website)  # Use the function directly
            tracker.mark_articles_as_seen(scraper_name, [news_item_data])

            return {
                "title": news_item.title,
                "s3_images_uploaded": 0,
                "status": "skipped",
                "sent_to_copywriter": False,
                "skip_reason": skip_reason,
                "banner_uploaded": False,
                "banner_s3_url": None
            }

        # Upload banner image synchronously (in this task)
        banner_s3_url = None
        if hasattr(news_item, 'banner_image') and news_item.banner_image:
            try:
                logger.info(f"[DEBUG] Uploading banner image synchronously: {news_item.banner_image}")
                banner_s3_key = f"{news_item.website.lower().replace(' ', '_')}/banner_{news_item.title[:30]}"

                # Upload banner image directly in this task (synchronously) with JPG conversion
                from services.s3_service import S3Service
                s3_service = S3Service()

                # Run async function in sync context
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    banner_s3_url = loop.run_until_complete(
                        s3_service.upload_image_from_url(
                            news_item.banner_image,
                            banner_s3_key,
                            convert_to_jpg=True  # Convert to JPG
                        )
                    )
                finally:
                    loop.close()

                if banner_s3_url:
                    logger.info(f"[DEBUG] Banner image uploaded and converted to JPG: {banner_s3_url}")
                else:
                    logger.warning(f"[DEBUG] Banner image upload failed")

            except Exception as e:
                logger.error(f"[DEBUG] Error uploading banner image: {e}")

        # Queue other images for background upload (excluding banner image)
        image_upload_jobs = []
        for i, image_url in enumerate(news_item.images):
            # Skip banner image since it's already processed
            if hasattr(news_item, 'banner_image') and image_url == news_item.banner_image:
                continue

            s3_key = f"{news_item.website.lower().replace(' ', '_')}/{news_item.title[:30]}_{i}"
            job = upload_image.apply_async(
                args=[image_url, s3_key, True],  # True = convert to JPG
                queue='uploads'
            )
            image_upload_jobs.append(job)

        # Prepare s3_image_urls list (banner first if available)
        s3_image_urls = []
        if banner_s3_url:
            s3_image_urls.append(banner_s3_url)

        # Create payload with banner image URL prioritized
        payload = CopywriterPayload(
            title=news_item.title,
            content=news_item.content,
            images=news_item.images,
            website=news_item.website,
            destination_website=news_item.destination_website,
            theme=news_item.theme,
            url=news_item.url,
            s3_image_urls=s3_image_urls,
            banner_image=banner_s3_url,
            original_post_url=news_item.url
        )

        # Send to copywriter
        content_processor.send_to_copywriter(payload)

        # Mark article as seen ONLY after successful processing
        from models.tracking import ScrapingTracker
        tracker = ScrapingTracker()
        scraper_name = _get_scraper_name(news_item.website)  # Use the function directly
        tracker.mark_articles_as_seen(scraper_name, [news_item_data])

        logger.info(f"[DEBUG] Successfully processed and sent article: {news_item.title}")

        return {
            "title": news_item.title,
            "s3_images_uploaded": len(image_upload_jobs) + (1 if banner_s3_url else 0),
            "status": "completed",
            "sent_to_copywriter": True,
            "image_jobs_queued": len(image_upload_jobs),
            "banner_uploaded": bool(banner_s3_url),
            "banner_s3_url": banner_s3_url
        }

    except Exception as exc:
        logger.error(f"[DEBUG] Processing task failed: {exc}")
        if self.request.retries < self.max_retries:
            logger.info(f"[DEBUG] Retrying in 30 seconds... (attempt {self.request.retries + 1})")
            raise self.retry(countdown=30)
        raise


@celery_app.task(bind=True, max_retries=3)
def upload_image(self, image_url: str, s3_key: str, convert_to_jpg: bool = True):
    """Celery task to upload an image to S3 with optional conversion"""
    try:
        from services.s3_service import S3Service

        logger.info(f"[DEBUG] Uploading image: {image_url}")

        s3_service = S3Service()

        # Run async function in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            s3_url = loop.run_until_complete(
                s3_service.upload_image_from_url(image_url, s3_key, convert_to_jpg)
            )
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
from celery import Celery
import os
import logging

logger = logging.getLogger(__name__)

# Use environment variables directly to avoid pydantic issues
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://redis:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://redis:6379/0')

# Initialize Celery
celery_app = Celery(
    "rss_agent",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=['core.tasks']
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_routes={
        'core.tasks.scrape_website': {'queue': 'scraping'},
        'core.tasks.process_news_item': {'queue': 'processing'},
        'core.tasks.upload_image': {'queue': 'uploads'},
    },
    worker_concurrency=4,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)


class QueueManager:
    def __init__(self):
        self.celery = celery_app

    def queue_scraping_job(self, scraper_name: str, priority: int = 5):
        """Queue a scraping job"""
        from core.tasks import scrape_website

        logger.info(f"[DEBUG] Queuing scraping job for {scraper_name}")
        result = scrape_website.apply_async(
            args=[scraper_name],
            priority=priority,
            queue='scraping'
        )
        return result.id

    def queue_processing_job(self, news_item_data: dict, priority: int = 5):
        """Queue a news processing job"""
        from core.tasks import process_news_item

        logger.info(f"[DEBUG] Queuing processing job for: {news_item_data.get('title', 'Unknown')}")
        result = process_news_item.apply_async(
            args=[news_item_data],
            priority=priority,
            queue='processing'
        )
        return result.id

    def queue_image_upload(self, image_url: str, s3_key: str, priority: int = 3):
        """Queue an image upload job"""
        from core.tasks import upload_image

        logger.info(f"[DEBUG] Queuing image upload: {image_url}")
        result = upload_image.apply_async(
            args=[image_url, s3_key],
            priority=priority,
            queue='uploads'
        )
        return result.id

    def get_job_status(self, job_id: str):
        """Get status of a job"""
        result = self.celery.AsyncResult(job_id)
        return {
            "id": job_id,
            "status": result.status,
            "result": result.result if result.ready() else None
        }
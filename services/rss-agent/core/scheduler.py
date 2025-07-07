from apscheduler.schedulers.asyncio import AsyncIOScheduler
from core.queue_manager import QueueManager
import logging

logger = logging.getLogger(__name__)


class NewsScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.queue_manager = QueueManager()

        # Import Riot sites dynamically
        from scrapers.config.riot_sites import get_all_riot_sites

        # List of all scrapers to check
        self.scrapers_to_check = [
            'league_of_legends',
            *get_all_riot_sites()
        ]

    async def check_for_updates(self):
        """Queue scraping jobs for all scrapers"""
        logger.info("[DEBUG] === STARTING HOURLY CHECK ===")

        job_ids = []
        for scraper_name in self.scrapers_to_check:
            try:
                job_id = self.queue_manager.queue_scraping_job(scraper_name)
                job_ids.append((scraper_name, job_id))
                logger.info(f"[DEBUG] Queued {scraper_name} with job ID: {job_id}")
            except Exception as e:
                logger.error(f"[DEBUG] Failed to queue {scraper_name}: {e}")

        logger.info(f"[DEBUG] Queued {len(job_ids)} scraping jobs")
        return job_ids

    def start(self):
        """Start the scheduler"""
        self.scheduler.add_job(
            self.check_for_updates,
            'interval',
            hours=1,
            id='news_check',
            max_instances=1  # Prevent overlapping runs
        )
        self.scheduler.start()
        logger.info("[DEBUG] Scheduler started - checking every hour")

    def stop(self):
        """Stop the scheduler"""
        self.scheduler.shutdown()
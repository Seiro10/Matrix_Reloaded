from fastapi import FastAPI
from contextlib import asynccontextmanager
from core.scheduler import NewsScheduler
from core.queue_manager import QueueManager
from config.settings import settings
import logging
import os

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO')),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Global instances
scheduler = NewsScheduler()
queue_manager = QueueManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("[DEBUG] Starting RSS Agent with Queue System...")
    scheduler.start()

    # Run initial check
    await scheduler.check_for_updates()

    yield

    # Shutdown
    logger.info("[DEBUG] Shutting down RSS Agent...")
    scheduler.stop()


app = FastAPI(
    title="RSS Gaming News Agent with Queue System",
    description="RSS agent for gaming news scraping with parallel processing",
    version="2.0.0",
    lifespan=lifespan
)


@app.get("/")
async def root():
    return {
        "message": "RSS Gaming News Agent with Queue System is running",
        "port": os.getenv('PORT', '8086'),
        "redis_url": settings.redis_url
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "queue_system": "active",
        "services": {
            "redis": "connected",
            "celery": "active"
        }
    }


@app.post("/manual-check")
async def manual_check():
    """Manually trigger a news check (queued)"""
    logger.info("[DEBUG] Manual check triggered")
    job_ids = await scheduler.check_for_updates()
    return {
        "message": "Manual check queued",
        "jobs": [{"scraper": name, "job_id": job_id} for name, job_id in job_ids]
    }


@app.post("/scrape/{scraper_name}")
async def scrape_specific(scraper_name: str):
    """Queue a specific scraper"""
    try:
        job_id = queue_manager.queue_scraping_job(scraper_name)
        return {"message": f"Scraping queued for {scraper_name}", "job_id": job_id}
    except Exception as e:
        return {"error": str(e)}


@app.get("/job/{job_id}")
async def get_job_status(job_id: str):
    """Get status of a specific job"""
    return queue_manager.get_job_status(job_id)


@app.get("/stats")
async def get_stats():
    """Get system statistics"""
    try:
        # Get Celery stats
        inspect = queue_manager.celery.control.inspect()
        active = inspect.active()
        scheduled = inspect.scheduled()

        return {
            "active_tasks": active,
            "scheduled_tasks": scheduled,
            "workers_online": list(active.keys()) if active else []
        }
    except Exception as e:
        return {"error": f"Could not get stats: {e}"}


@app.get("/debug-scrape/{scraper_name}")
async def debug_scrape(scraper_name: str):
    """Debug what the scraper sees"""
    try:
        if scraper_name == "league_of_legends":
            from scrapers.stuffgaming.league_of_legends import LeagueOfLegendsScraper
            scraper = LeagueOfLegendsScraper()

            # Get the raw HTML to inspect
            soup = scraper.fetch_page(scraper.base_url)

            # Find different types of potential article containers
            debug_info = {
                "url": scraper.base_url,
                "title": soup.title.string if soup.title else "No title",
                "articles": len(soup.find_all('article')),
                "divs_with_news": len(soup.find_all('div', class_=lambda x: x and 'news' in x.lower())),
                "divs_with_article": len(soup.find_all('div', class_=lambda x: x and 'article' in x.lower())),
                "divs_with_post": len(soup.find_all('div', class_=lambda x: x and 'post' in x.lower())),
                "divs_with_card": len(soup.find_all('div', class_=lambda x: x and 'card' in x.lower())),
                "all_links": len(soup.find_all('a', href=True)),
                "h1_count": len(soup.find_all('h1')),
                "h2_count": len(soup.find_all('h2')),
                "h3_count": len(soup.find_all('h3')),
            }

            # Get sample class names to understand the structure
            sample_classes = []
            for div in soup.find_all('div', class_=True)[:20]:
                if div.get('class'):
                    sample_classes.extend(div.get('class'))

            debug_info["sample_classes"] = list(set(sample_classes))[:30]

            # Get first few links with their text
            links_sample = []
            for link in soup.find_all('a', href=True)[:10]:
                links_sample.append({
                    "text": link.get_text(strip=True)[:100],
                    "href": link.get('href'),
                    "class": link.get('class')
                })

            debug_info["sample_links"] = links_sample

            return debug_info
        else:
            return {"error": f"Unknown scraper: {scraper_name}"}

    except Exception as e:
        return {"error": str(e)}


@app.get("/tracking/stats")
async def get_tracking_stats():
    """Get tracking statistics for all scrapers"""
    try:
        from models.tracking import ScrapingTracker
        tracker = ScrapingTracker()
        return tracker.get_stats()
    except Exception as e:
        return {"error": str(e)}


@app.get("/tracking/stats/{scraper_name}")
async def get_scraper_stats(scraper_name: str):
    """Get tracking statistics for a specific scraper"""
    try:
        from models.tracking import ScrapingTracker
        tracker = ScrapingTracker()
        return tracker.get_stats(scraper_name)
    except Exception as e:
        return {"error": str(e)}


@app.post("/tracking/reset/{scraper_name}")
async def reset_scraper_tracking(scraper_name: str):
    """Reset tracking for a specific scraper (for testing)"""
    try:
        from models.tracking import ScrapingTracker
        tracker = ScrapingTracker()

        # Remove scraper data
        if scraper_name in tracker.data["scrapers"]:
            del tracker.data["scrapers"][scraper_name]

        # Remove articles from this scraper
        articles_to_remove = [
            url for url, data in tracker.data["articles"].items()
            if data.get("scraper") == scraper_name
        ]

        for url in articles_to_remove:
            del tracker.data["articles"][url]

        tracker._save_data()

        return {
            "message": f"Reset tracking for {scraper_name}",
            "removed_articles": len(articles_to_remove)
        }
    except Exception as e:
        return {"error": str(e)}


@app.get("/tracking/new-check/{scraper_name}")
async def simulate_new_check(scraper_name: str):
    """Simulate checking for new articles without processing them"""
    try:
        if scraper_name == "league_of_legends":
            from scrapers.stuffgaming.league_of_legends import LeagueOfLegendsScraper
            scraper = LeagueOfLegendsScraper()
        elif scraper_name == "test_scraper":
            from scrapers.stuffgaming.test_scraper import TestScraper
            scraper = TestScraper()
        else:
            return {"error": f"Unknown scraper: {scraper_name}"}

        # Get all articles
        news_items = scraper.scrape_news()

        return {
            "scraper": scraper_name,
            "new_articles_found": len(news_items),
            "articles": [
                {
                    "title": item.title,
                    "url": item.url,
                    "published_date": item.published_date.isoformat()
                }
                for item in news_items
            ]
        }
    except Exception as e:
        return {"error": str(e)}


@app.get("/debug/tracking-file")
async def debug_tracking_file():
    """Debug tracking file location and content"""
    try:
        from models.tracking import ScrapingTracker
        import os

        tracker = ScrapingTracker()
        debug_info = tracker.get_debug_info()

        return {
            **debug_info,
            "current_data": tracker.data,
            "data_keys": list(tracker.data.keys()) if tracker.data else None
        }
    except Exception as e:
        return {"error": str(e)}


@app.post("/debug/force-tracking-save")
async def force_tracking_save():
    """Force save tracking data for debugging"""
    try:
        from models.tracking import ScrapingTracker

        tracker = ScrapingTracker()

        # Add some test data
        test_articles = [
            {
                "url": "https://test.com/article1",
                "title": "Test Article 1"
            }
        ]

        tracker.mark_articles_as_seen("debug_test", test_articles)

        return {
            "message": "Forced tracking save completed",
            "stats": tracker.get_stats()
        }
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv('PORT', 8086))
    uvicorn.run(app, host="0.0.0.0", port=port)
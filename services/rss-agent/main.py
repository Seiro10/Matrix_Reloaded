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
        if scraper_name == "test_scraper":
            from scrapers.stuffgaming.test_scraper import TestScraper
            scraper = TestScraper()
        else:
            # Use unified scraper for all other sites
            from scrapers.stuffgaming.unified_riot_scraper import UnifiedRiotScraper
            scraper = UnifiedRiotScraper(scraper_name)

        # Get the raw HTML to inspect
        soup = scraper.fetch_page(scraper.base_url)

        # Debug info
        debug_info = {
            "scraper": scraper_name,
            "url": scraper.base_url,
            "title": soup.title.string if soup.title else "No title",
            "articles": len(soup.find_all('article')),
            "all_links": len(soup.find_all('a', href=True)),
            "news_links": len(soup.find_all('a', href=lambda x: x and '/news/' in x)),
            "banner_testid_exists": bool(soup.find('img', {'data-testid': 'banner-image'})),
            "banner_class_exists": bool(soup.find('img', class_='banner-image')),
            "html_length": len(str(soup)),
            "use_playwright": getattr(scraper, 'use_playwright', False)
        }

        return debug_info

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


@app.delete("/tracking/reset/{scraper_name}")
async def reset_tracking(scraper_name: str):
    """Reset tracking for a specific scraper"""
    try:
        from models.tracking import ScrapingTracker
        tracker = ScrapingTracker()

        # Reset the scraper's data
        if scraper_name in tracker.data["scrapers"]:
            tracker.data["scrapers"][scraper_name] = {
                "seen_urls": [],
                "last_run": None
            }

            # Remove articles for this scraper
            articles_to_remove = [
                url for url, data in tracker.data["articles"].items()
                if data.get("scraper") == scraper_name
            ]

            for url in articles_to_remove:
                del tracker.data["articles"][url]

            tracker._save_data()

            return {
                "success": True,
                "message": f"Reset tracking for {scraper_name}",
                "removed_urls": len(articles_to_remove)
            }
        else:
            return {
                "success": False,
                "message": f"Scraper {scraper_name} not found"
            }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


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


@app.get("/debug/reset-all-tracking")
async def reset_all_tracking():
    """Reset all tracking data for debugging"""
    try:
        from models.tracking import ScrapingTracker
        tracker = ScrapingTracker()

        # Clear all data
        tracker.data = {
            "scrapers": {},
            "articles": {}
        }
        tracker._save_data()

        return {
            "message": "All tracking data reset",
            "scrapers_cleared": True,
            "articles_cleared": True
        }
    except Exception as e:
        return {"error": str(e)}


@app.get("/test-s3")
async def test_s3():
    """Test S3 connection and upload"""
    try:
        from services.s3_service import S3Service
        s3_service = S3Service()

        if not s3_service.s3_client:
            return {"status": "error", "message": "S3 client not initialized"}

        # Test with a simple text file
        test_content = "Test file for S3 upload - RSS Agent"
        test_key = "test/rss-agent-test.txt"

        s3_service.s3_client.put_object(
            Bucket=s3_service.bucket_name,
            Key=test_key,
            Body=test_content.encode(),
            ContentType="text/plain"
        )

        test_url = f"https://{s3_service.bucket_name}.s3.{s3_service.s3_client._client_config.region_name}.amazonaws.com/{test_key}"

        return {
            "status": "success",
            "message": "S3 upload test successful",
            "test_file_url": test_url,
            "bucket": s3_service.bucket_name
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "error_type": type(e).__name__
        }


@app.get("/debug/aws")
async def debug_aws():
    """Debug AWS configuration"""
    from config.settings import settings
    import os

    return {
        "aws_access_key_set": bool(settings.aws_access_key_id),
        "aws_secret_key_set": bool(settings.aws_secret_access_key),
        "s3_bucket": settings.s3_bucket_name,
        "s3_region": settings.s3_region,
        "access_key_length": len(settings.aws_access_key_id) if settings.aws_access_key_id else 0,
        "secret_key_length": len(settings.aws_secret_access_key) if settings.aws_secret_access_key else 0,
        # Check environment variables directly
        "env_aws_access_key_set": bool(os.getenv('AWS_ACCESS_KEY_ID')),
        "env_aws_secret_key_set": bool(os.getenv('AWS_SECRET_ACCESS_KEY')),
        "env_access_key_length": len(os.getenv('AWS_ACCESS_KEY_ID', '')),
        "env_secret_key_length": len(os.getenv('AWS_SECRET_ACCESS_KEY', ''))
    }


@app.get("/debug-banner/{scraper_name}")
async def debug_banner(scraper_name: str):
    """Debug banner image extraction"""
    try:
        from scrapers.stuffgaming.unified_riot_scraper import UnifiedRiotScraper

        scraper = UnifiedRiotScraper(scraper_name)
        soup = scraper.fetch_page(scraper.base_url)

        # Test banner extraction
        banner_image = scraper.extract_banner_image(
            soup,
            scraper.config.banner_selectors,
            scraper.base_url.split('/fr-fr')[0]
        )

        # Check if banner elements exist
        banner_testid = soup.find('img', {'data-testid': 'banner-image'})
        banner_class = soup.find('img', class_='banner-image')

        return {
            "scraper": scraper_name,
            "base_url": scraper.base_url,
            "banner_found": banner_image,
            "banner_testid_exists": bool(banner_testid),
            "banner_class_exists": bool(banner_class),
            "banner_testid_src": banner_testid.get('src') if banner_testid else None,
            "banner_class_src": banner_class.get('src') if banner_class else None,
            "html_contains_testid": 'data-testid="banner-image"' in str(soup),
            "html_length": len(str(soup))
        }

    except Exception as e:
        return {"error": str(e)}


@app.get("/test-playwright-install")
async def test_playwright_install():
    """Test Playwright installation"""
    import subprocess
    import os
    try:

        # Check if Playwright is installed
        result = subprocess.run(
            ["python", "-m", "playwright", "install-deps"],
            capture_output=True,
            text=True,
            cwd="/app"
        )

        # Try to use Playwright
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto("https://example.com")
            title = page.title()
            browser.close()

        return {
            "status": "success",
            "playwright_working": True,
            "test_title": title,
            "user": os.getenv("USER", "unknown"),
            "home": os.getenv("HOME", "unknown")
        }
    except Exception as e:
        return {
            "status": "error",
            "playwright_working": False,
            "error": str(e),
            "user": os.getenv("USER", "unknown"),
            "home": os.getenv("HOME", "unknown")
        }


@app.get("/force-playwright-install")
async def force_playwright_install():
    """Force install Playwright browsers"""
    try:
        import subprocess
        import os

        # Try to install Playwright browsers
        result = subprocess.run(
            ["python", "-m", "playwright", "install", "chromium"],
            capture_output=True,
            text=True,
            cwd="/app"
        )

        install_output = result.stdout + result.stderr

        # Test if it works
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto("https://example.com")
            title = page.title()
            browser.close()

        return {
            "status": "success",
            "playwright_installed": True,
            "install_output": install_output,
            "test_title": title
        }
    except Exception as e:
        return {
            "status": "error",
            "playwright_installed": False,
            "error": str(e),
            "install_output": install_output if 'install_output' in locals() else "No output"
        }

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv('PORT', 8086))
    uvicorn.run(app, host="0.0.0.0", port=port)
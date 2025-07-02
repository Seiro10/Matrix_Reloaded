from pydantic import BaseModel
from typing import Dict, List, Set
from datetime import datetime
import json
import os
import logging
import tempfile

logger = logging.getLogger(__name__)


class ScrapingTracker:
    def __init__(self, storage_file: str = "/app/data/scraping_tracker.json"):
        self.storage_file = storage_file
        self.fallback_file = "/tmp/scraping_tracker.json"  # ✅ Fallback dans /tmp
        self.data = self._load_data()

    def _get_writable_file(self) -> str:
        """Get a writable file path"""
        # Try the main storage file first
        if self._test_write_permissions(self.storage_file):
            return self.storage_file

        # Fallback to /tmp
        logger.warning(f"[DEBUG] Cannot write to {self.storage_file}, using fallback: {self.fallback_file}")
        return self.fallback_file

    def _test_write_permissions(self, filepath: str) -> bool:
        """Test if we can write to a file path"""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(filepath), exist_ok=True)

            # Test write by creating a temp file in the same directory
            test_file = f"{filepath}.test"
            with open(test_file, 'w') as f:
                f.write("test")
            os.remove(test_file)
            return True
        except Exception as e:
            logger.error(f"[DEBUG] Cannot write to {filepath}: {e}")
            return False

    def _load_data(self) -> Dict:
        """Load tracking data from file"""
        # Try to load from main file first
        for filepath in [self.storage_file, self.fallback_file]:
            if os.path.exists(filepath):
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    logger.info(f"[DEBUG] Loaded tracking data from: {filepath}")
                    logger.info(
                        f"[DEBUG] Data contains: {len(data.get('scrapers', {}))} scrapers, {len(data.get('articles', {}))} articles")
                    return data
                except Exception as e:
                    logger.error(f"[DEBUG] Error loading tracking data from {filepath}: {e}")

        logger.info(f"[DEBUG] No existing tracking file found, creating new data")
        default_data = {
            "scrapers": {},
            "articles": {}
        }

        # Try to save initial data
        try:
            self._save_data_internal(default_data)
        except Exception as e:
            logger.error(f"[DEBUG] Error saving initial tracking data: {e}")

        return default_data

    def _save_data_internal(self, data: Dict = None):
        """Internal save method with fallback"""
        data_to_save = data or self.data

        # Get writable file path
        filepath = self._get_writable_file()

        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(filepath), exist_ok=True)

            # Write to temporary file first, then move (atomic operation)
            temp_file = f"{filepath}.tmp"
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, indent=2, ensure_ascii=False, default=str)

            # Move temp file to final location
            os.rename(temp_file, filepath)

            logger.info(f"[DEBUG] Tracking data saved successfully to {filepath}")

        except Exception as e:
            logger.error(f"[DEBUG] Error saving tracking data to {filepath}: {e}")
            # Try fallback location if main location failed
            if filepath != self.fallback_file:
                try:
                    logger.info(f"[DEBUG] Trying fallback location: {self.fallback_file}")
                    with open(self.fallback_file, 'w', encoding='utf-8') as f:
                        json.dump(data_to_save, f, indent=2, ensure_ascii=False, default=str)
                    logger.info(f"[DEBUG] Successfully saved to fallback location")
                except Exception as e2:
                    logger.error(f"[DEBUG] Fallback save also failed: {e2}")
                    raise e2
            else:
                raise e

    def _save_data(self):
        """Save tracking data to file"""
        self._save_data_internal()

    def get_seen_urls(self, scraper_name: str) -> Set[str]:
        """Get set of URLs already seen by this scraper"""
        scraper_data = self.data["scrapers"].get(scraper_name, {})
        seen_urls = set(scraper_data.get("seen_urls", []))
        logger.info(f"[DEBUG] Scraper {scraper_name} has {len(seen_urls)} seen URLs")
        return seen_urls

    def get_last_run(self, scraper_name: str) -> datetime:
        """Get last run time for scraper"""
        scraper_data = self.data["scrapers"].get(scraper_name, {})
        last_run_str = scraper_data.get("last_run")
        if last_run_str:
            try:
                last_run = datetime.fromisoformat(last_run_str)
                logger.info(f"[DEBUG] Last run for {scraper_name}: {last_run}")
                return last_run
            except Exception as e:
                logger.error(f"[DEBUG] Error parsing last run date: {e}")

        logger.info(f"[DEBUG] No previous run found for {scraper_name}")
        return datetime.min

    def mark_articles_as_seen(self, scraper_name: str, articles: List[dict]):
        """Mark articles as seen and update tracking"""
        logger.info(f"[DEBUG] Marking {len(articles)} articles as seen for {scraper_name}")

        now = datetime.now()

        # Initialize scraper data if not exists
        if scraper_name not in self.data["scrapers"]:
            self.data["scrapers"][scraper_name] = {
                "seen_urls": [],
                "last_run": None
            }
            logger.info(f"[DEBUG] Initialized new scraper tracking for {scraper_name}")

        seen_urls = set(self.data["scrapers"][scraper_name]["seen_urls"])
        new_urls_count = 0

        # Process each article
        for article in articles:
            url = article.get("url", "")
            title = article.get("title", "")

            if url:
                # Add to seen URLs
                if url not in seen_urls:
                    new_urls_count += 1
                seen_urls.add(url)

                # Track article details
                if url not in self.data["articles"]:
                    self.data["articles"][url] = {
                        "title": title,
                        "first_seen": now.isoformat(),
                        "last_seen": now.isoformat(),
                        "scraper": scraper_name
                    }
                else:
                    self.data["articles"][url]["last_seen"] = now.isoformat()

        # Update scraper data
        self.data["scrapers"][scraper_name]["seen_urls"] = list(seen_urls)
        self.data["scrapers"][scraper_name]["last_run"] = now.isoformat()

        # Keep only last 1000 URLs per scraper
        if len(seen_urls) > 1000:
            recent_urls = list(seen_urls)[-1000:]
            self.data["scrapers"][scraper_name]["seen_urls"] = recent_urls

        logger.info(f"[DEBUG] Added {new_urls_count} new URLs, total seen: {len(seen_urls)}")

        try:
            self._save_data()
            logger.info(f"[DEBUG] Successfully saved tracking data for {scraper_name}")
        except Exception as e:
            logger.error(f"[DEBUG] Failed to save tracking data: {e}")

    def filter_new_articles(self, scraper_name: str, articles: List[dict]) -> List[dict]:
        """Filter out articles that have already been seen"""
        seen_urls = self.get_seen_urls(scraper_name)

        new_articles = []
        for article in articles:
            url = article.get("url", "")
            if url and url not in seen_urls:
                new_articles.append(article)

        logger.info(
            f"[DEBUG] Filtered {len(articles)} articles: {len(new_articles)} new, {len(articles) - len(new_articles)} already seen")
        return new_articles

    def get_stats(self, scraper_name: str = None) -> Dict:
        """Get tracking statistics"""
        if scraper_name:
            scraper_data = self.data["scrapers"].get(scraper_name, {})
            return {
                "scraper": scraper_name,
                "total_seen_urls": len(scraper_data.get("seen_urls", [])),
                "last_run": scraper_data.get("last_run"),
                "total_articles_tracked": len([
                    url for url, data in self.data["articles"].items()
                    if data.get("scraper") == scraper_name
                ])
            }
        else:
            return {
                "total_scrapers": len(self.data["scrapers"]),
                "total_articles": len(self.data["articles"]),
                "scrapers": {
                    name: {
                        "seen_urls": len(data.get("seen_urls", [])),
                        "last_run": data.get("last_run")
                    }
                    for name, data in self.data["scrapers"].items()
                }
            }

    def get_debug_info(self) -> Dict:
        """Get debug information about file locations and permissions"""
        return {
            "primary_file": self.storage_file,
            "fallback_file": self.fallback_file,
            "primary_exists": os.path.exists(self.storage_file),
            "fallback_exists": os.path.exists(self.fallback_file),
            "primary_writable": self._test_write_permissions(self.storage_file),
            "fallback_writable": self._test_write_permissions(self.fallback_file),
            "current_data_size": len(str(self.data)),
            "writable_file": self._get_writable_file()
        }
from typing import List
from datetime import datetime
import re
from scrapers.base_scraper import BaseScraper
from models.schemas import NewsItem
from models.tracking import ScrapingTracker
from config.websites import get_destination_website
from scrapers.config.riot_sites import get_riot_site_config
import logging

logger = logging.getLogger(__name__)


class RiotGamesScraper(BaseScraper):
    def __init__(self, site_key: str):
        """Initialize scraper for a specific Riot Games site"""
        site_config = get_riot_site_config(site_key)
        if not site_config:
            raise ValueError(f"Unknown Riot site: {site_key}")

        super().__init__(
            base_url=site_config["url"],
            website_name=site_config["website_name"],
            theme=site_config["theme"]
        )

        self.site_key = site_key
        self.max_articles = site_config["max_articles"]
        self.tracker = ScrapingTracker()

    def scrape_news(self) -> List[NewsItem]:
        """Scrape news from the Riot Games site - only new articles"""
        logger.info(f"[DEBUG] Starting scrape for {self.website_name} ({self.site_key})")

        try:
            soup = self.fetch_page(self.base_url)
            logger.info(f"[DEBUG] Successfully fetched main page: {self.base_url}")

            # Get last run time
            last_run = self.tracker.get_last_run(self.site_key)
            logger.info(f"[DEBUG] Last run was: {last_run}")

            all_news_items = []

            # Use the same extraction logic as League of Legends
            article_links = soup.find_all('a',
                                          class_=['sc-985df63-0', 'cGQgsO', 'sc-d043b2-0', 'bZMlAb', 'sc-86f2e710-5',
                                                  'eFeRux', 'action'])

            logger.info(f"[DEBUG] Found {len(article_links)} article links with specific classes")

            # Fallback approach (same as League of Legends)
            if not article_links:
                all_links = soup.find_all('a', href=True)
                article_links = []
                for link in all_links:
                    href = link.get('href', '')
                    text = link.get_text(strip=True)

                    if (('/news/' in href or '/fr-fr/news/' in href) and
                            text and len(text) > 10 and
                            not href.startswith('https://merch.') and
                            not 'utm_' in href):
                        article_links.append(link)

                logger.info(f"[DEBUG] Fallback found {len(article_links)} news links")

            # Limit to max_articles
            article_links = article_links[:self.max_articles]
            logger.info(f"[DEBUG] Limited to {len(article_links)} articles (max: {self.max_articles})")

            # Extract articles
            for i, link in enumerate(article_links):
                try:
                    news_item = self._extract_article_data(link, i)
                    if news_item and news_item.title and len(news_item.title) > 5:
                        all_news_items.append(news_item)
                        logger.info(f"[DEBUG] Successfully extracted article {i + 1}: {news_item.title[:50]}...")
                    else:
                        logger.warning(f"[DEBUG] Skipped invalid article {i + 1}")
                except Exception as e:
                    logger.error(f"[DEBUG] Error extracting article {i + 1}: {e}")
                    continue

            logger.info(f"[DEBUG] Total extracted articles: {len(all_news_items)}")

            # Filter for new articles only
            articles_data = [item.model_dump() for item in all_news_items]
            new_articles_data = self.tracker.filter_new_articles(self.site_key, articles_data)

            logger.info(f"[DEBUG] New articles found: {len(new_articles_data)} out of {len(articles_data)}")

            # Convert back to NewsItem objects
            new_news_items = [NewsItem(**article_data) for article_data in new_articles_data]

            # ❌ REMOVED: Don't mark articles as seen here anymore!
            # Articles will be marked as seen only after successful processing in the Celery task

            return new_news_items

        except Exception as e:
            logger.error(f"[DEBUG] Error in scrape_news for {self.site_key}: {e}")
            return []
        

    def _extract_article_data(self, link, index) -> NewsItem:
        """Extract data from a news link (same logic as League of Legends)"""
        # Extract URL
        href = link.get('href', '')
        base_domain = self.base_url.split('/fr-fr')[0]  # Get base domain

        if href.startswith('/'):
            article_url = f"{base_domain}{href}"
        elif href.startswith('http'):
            article_url = href
        else:
            article_url = f"{base_domain}/fr-fr/news/{href}"

        # Extract title and basic info from link text (same logic)
        link_text = link.get_text(strip=True)
        parts = link_text.split('\n') if '\n' in link_text else [link_text]

        category = ""
        date_str = ""
        title = ""
        description = ""

        if len(parts) >= 1:
            first_part = parts[0]
            date_match = re.search(r'(\d{2}/\d{2}/\d{4})', first_part)
            if date_match:
                date_str = date_match.group(1)
                category = first_part[:date_match.start()].strip()
                title_start = first_part[date_match.end():].strip()
                if title_start:
                    title = title_start
            else:
                title = first_part

        if len(parts) > 1:
            description = ' '.join(parts[1:]).strip()

        if not title:
            title = link_text[:100].strip()

        if category:
            title = f"[{category}] {title}"

        # Extract content and images (same logic as League of Legends)
        content = description if description else f"{self.website_name} news article"
        images = []

        if article_url and article_url.startswith(base_domain):
            try:
                logger.info(f"[DEBUG] Fetching full article content from: {article_url}")
                article_soup = self.fetch_page(article_url)

                full_content = self._extract_full_content(article_soup)
                if len(full_content) > len(content):
                    content = full_content

                images = self.extract_images(article_soup, base_domain)
                logger.info(f"[DEBUG] Extracted {len(images)} images from full article")

            except Exception as e:
                logger.warning(f"[DEBUG] Could not fetch full article content: {e}")

        # Parse date
        published_date = datetime.now()
        if date_str:
            try:
                published_date = datetime.strptime(date_str, "%d/%m/%Y")
            except Exception as e:
                logger.warning(f"[DEBUG] Could not parse date '{date_str}': {e}")

        # Remove duplicate images and limit
        images = list(dict.fromkeys(images))[:3]

        return NewsItem(
            title=title.strip(),
            content=content.strip()[:2000],
            images=images,
            website=self.website_name,
            destination_website=get_destination_website(self.website_name),
            theme=self.theme,
            url=article_url,
            published_date=published_date
        )

    def _extract_full_content(self, soup) -> str:
        """Extract full content from article page (same as League of Legends)"""
        content_selectors = [
            'article', '[role="main"]', '.content', '.article-content', '.post-content',
            '.news-content', 'main', '[class*="content"]', '[class*="article"]',
            'div[class*="sc-"]', 'div[class*="text"]', 'div[class*="body"]', 'p'
        ]

        content_parts = []
        for selector in content_selectors:
            elements = soup.select(selector)
            for element in elements:
                if element:
                    for unwanted in element(["script", "style", "nav", "footer", "header", "aside"]):
                        unwanted.decompose()

                    text = element.get_text(separator=' ', strip=True)
                    if len(text) > 50 and text not in content_parts:
                        content_parts.append(text)

        full_content = ' '.join(content_parts)
        full_content = re.sub(r'\s+', ' ', full_content).strip()
        return full_content[:2000] if full_content else ""
from typing import List, Optional
from datetime import datetime
import re
from scrapers.base_scraper import BaseScraper
from models.schemas import NewsItem
from models.tracking import ScrapingTracker
from config.websites import get_destination_website
from scrapers.config.scraper_configs import get_scraper_config
import logging

logger = logging.getLogger(__name__)


class UnifiedRiotScraper(BaseScraper):
    def __init__(self, scraper_key: str):
        """Initialize scraper for any configured site"""
        config = get_scraper_config(scraper_key)
        if not config:
            raise ValueError(f"Unknown scraper key: {scraper_key}")

        # Enable Playwright for Riot Games sites (they use React/JS)
        super().__init__(
            base_url=config.url,
            website_name=config.website_name,
            theme=config.theme,
            use_playwright=True  # Enable Playwright for JS-rendered content
        )

        self.scraper_key = scraper_key
        self.config = config
        self.tracker = ScrapingTracker()

    def scrape_news(self) -> List[NewsItem]:
        """Scrape news from the configured site - only new articles"""
        logger.info(f"[DEBUG] Starting scrape for {self.website_name} ({self.scraper_key})")

        try:
            soup = self.fetch_page(self.base_url)
            logger.info(f"[DEBUG] Successfully fetched main page: {self.base_url}")

            all_news_items = []

            # Use configured article selectors
            article_links = []
            for selector in self.config.article_selectors:
                links = soup.select(selector)
                article_links.extend(links)
                if links:
                    logger.info(f"[DEBUG] Found {len(links)} links with selector: {selector}")

            # Fallback approach if no configured selectors work
            if not article_links:
                logger.info("[DEBUG] No articles found with configured selectors, using fallback")
                article_links = self._fallback_article_extraction(soup)

            # Limit to max_articles
            article_links = article_links[:self.config.max_articles]
            logger.info(f"[DEBUG] Processing {len(article_links)} articles (max: {self.config.max_articles})")

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

            # Filter for new articles only
            articles_data = [item.model_dump() for item in all_news_items]
            new_articles_data = self.tracker.filter_new_articles(self.scraper_key, articles_data)

            logger.info(f"[DEBUG] New articles found: {len(new_articles_data)} out of {len(articles_data)}")

            # Convert back to NewsItem objects
            new_news_items = [NewsItem(**article_data) for article_data in new_articles_data]

            return new_news_items

        except Exception as e:
            logger.error(f"[DEBUG] Error in scrape_news for {self.scraper_key}: {e}")
            return []

    def _fallback_article_extraction(self, soup):
        """Enhanced fallback method for article extraction using stable selectors"""
        article_links = []

        # Strategy 1: Look for links containing '/news/' in href
        news_links = soup.find_all('a', href=lambda x: x and '/news/' in x)
        for link in news_links:
            href = link.get('href', '')
            text = link.get_text(strip=True)

            # Filter out unwanted links
            if (text and len(text) > 10 and
                    not href.startswith('https://merch.') and
                    not 'utm_' in href and
                    not any(skip in href.lower() for skip in ['login', 'register', 'account', 'support'])):
                article_links.append(link)

        # Strategy 2: Look for links in news containers
        news_containers = soup.find_all(['div', 'section'], class_=lambda x: x and 'news' in ' '.join(x).lower())
        for container in news_containers:
            links = container.find_all('a', href=True)
            for link in links:
                href = link.get('href', '')
                text = link.get_text(strip=True)

                if (text and len(text) > 10 and
                        ('/news/' in href or '/fr-fr/news/' in href) and
                        link not in article_links):
                    article_links.append(link)

        # Strategy 3: Look for article tags with links
        articles = soup.find_all('article')
        for article in articles:
            link = article.find('a', href=True)
            if link and link not in article_links:
                href = link.get('href', '')
                text = link.get_text(strip=True)

                if text and len(text) > 10:
                    article_links.append(link)

        logger.info(f"[DEBUG] Enhanced fallback found {len(article_links)} news links")
        return article_links

    def _extract_article_data(self, link, index) -> NewsItem:
        """Extract data from a news link with banner image support"""
        # Extract URL
        href = link.get('href', '')
        base_domain = self.base_url.split('/fr-fr')[0]

        if href.startswith('/'):
            article_url = f"{base_domain}{href}"
        elif href.startswith('http'):
            article_url = href
        else:
            article_url = f"{base_domain}/fr-fr/news/{href}"

        # Extract title and basic info from link text
        link_text = link.get_text(strip=True)
        title, description, published_date = self._parse_link_text(link_text)

        # Extract content and images
        content = description if description else f"{self.website_name} news article"
        banner_image = None
        other_images = []

        if article_url and article_url.startswith(base_domain):
            try:
                logger.info(f"[DEBUG] Fetching full article content from: {article_url}")
                article_soup = self.fetch_page(article_url)

                # Extract banner image and other images separately
                banner_image, other_images = self.extract_images_with_banner(
                    article_soup,
                    self.config.banner_selectors,
                    base_domain
                )

                if banner_image:
                    logger.info(f"[DEBUG] Found banner image: {banner_image}")
                logger.info(f"[DEBUG] Found {len(other_images)} other images")

                # Extract full content
                full_content = self._extract_full_content(article_soup)
                if len(full_content) > len(content):
                    content = full_content

            except Exception as e:
                logger.warning(f"[DEBUG] Could not fetch full article content: {e}")

        # Prepare images list (banner first, then others)
        all_images = []
        if banner_image:
            all_images.append(banner_image)
        all_images.extend(other_images[:2])  # Limit other images

        # Remove duplicates
        all_images = list(dict.fromkeys(all_images))

        return NewsItem(
            title=title.strip(),
            content=content.strip()[:2000],
            images=all_images,
            website=self.website_name,
            destination_website=get_destination_website(self.website_name),
            theme=self.theme,
            url=article_url,
            published_date=published_date,
            banner_image=banner_image  # Add banner image separately
        )

    def _parse_link_text(self, link_text: str) -> tuple[str, str, datetime]:
        """Parse link text to extract title, description, and date"""
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

        # Parse date
        published_date = datetime.now()
        if date_str:
            try:
                published_date = datetime.strptime(date_str, "%d/%m/%Y")
            except Exception as e:
                logger.warning(f"[DEBUG] Could not parse date '{date_str}': {e}")

        return title, description, published_date

    def _extract_full_content(self, soup) -> str:
        """Extract full content from article page"""
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
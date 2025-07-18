from typing import List, Optional
from datetime import datetime
import re
from scrapers.base_scraper import BaseScraper
from models.schemas import NewsItem
from models.tracking import ScrapingTracker
from config.websites import get_destination_website
import logging

logger = logging.getLogger(__name__)


class BlizzardNewsScraper(BaseScraper):
    def __init__(self):
        super().__init__(
            base_url="https://news.blizzard.com/fr-fr",
            website_name="Blizzard News",
            theme="Gaming",
            use_playwright=True  # May need JS rendering for custom components
        )
        self.tracker = ScrapingTracker()

    def scrape_news(self) -> List[NewsItem]:
        """Scrape news from Blizzard News - only new articles"""
        logger.info(f"[DEBUG] Starting scrape for {self.website_name}")

        try:
            soup = self.fetch_page(self.base_url)
            logger.info(f"[DEBUG] Successfully fetched main page: {self.base_url}")

            all_news_items = []

            # Find the featured news section
            featured_news = soup.find('blz-news', class_='featured-news')
            if not featured_news:
                logger.warning("[DEBUG] No featured-news section found")
                return []

            # Extract all news cards
            news_cards = featured_news.find_all('blz-news-card')
            logger.info(f"[DEBUG] Found {len(news_cards)} news cards")

            # Process each news card
            for i, card in enumerate(news_cards):
                try:
                    news_item = self._extract_article_data(card, i)
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
            new_articles_data = self.tracker.filter_new_articles("blizzard_news", articles_data)

            logger.info(f"[DEBUG] New articles found: {len(new_articles_data)} out of {len(articles_data)}")

            # Convert back to NewsItem objects
            new_news_items = [NewsItem(**article_data) for article_data in new_articles_data]

            return new_news_items

        except Exception as e:
            logger.error(f"[DEBUG] Error in scrape_news for Blizzard News: {e}")
            return []

    def _extract_article_data(self, card, index) -> Optional[NewsItem]:
        """Extract data from a news card"""
        try:
            # Extract URL from href attribute
            href = card.get('href', '')
            if not href:
                # Try to find a link inside the card
                link_element = card.find('a', href=True)
                if link_element:
                    href = link_element.get('href', '')
                else:
                    logger.warning(f"[DEBUG] No href found in card {index}")
                    return None

            # Build full URL
            if href.startswith('/'):
                article_url = f"https://news.blizzard.com{href}"
            elif href.startswith('http'):
                article_url = href
            else:
                article_url = f"https://news.blizzard.com/fr-fr{href}"

            logger.info(f"[DEBUG] Processing article URL: {article_url}")

            # Fetch individual article page with error handling
            try:
                article_soup = self.fetch_page(article_url)
            except Exception as e:
                logger.error(f"[DEBUG] Failed to fetch article page {article_url}: {e}")
                return None

            # Extract title from h1 slot="heading"
            title_element = article_soup.find('h1', {'slot': 'heading'})
            if not title_element:
                # Fallback: try regular h1
                title_element = article_soup.find('h1')

            title = title_element.get_text(strip=True) if title_element else f"Blizzard News Article {index + 1}"

            # Extract banner image from blz-image
            banner_image = None
            blz_image = article_soup.find('blz-image')
            if blz_image:
                banner_src = blz_image.get('src', '')
                if banner_src:
                    if banner_src.startswith('http'):
                        banner_image = banner_src
                    elif banner_src.startswith('/'):
                        banner_image = f"https://news.blizzard.com{banner_src}"

            # Extract content from section class="blog"
            content = ""
            blog_section = article_soup.find('section', class_='blog')
            if blog_section:
                # Remove unwanted elements
                for unwanted in blog_section(['script', 'style', 'nav', 'footer', 'header']):
                    unwanted.decompose()

                content = blog_section.get_text(separator=' ', strip=True)
                content = re.sub(r'\s+', ' ', content)[:2000]  # Limit content length

            if not content:
                content = "Blizzard News article content"

            # Extract additional images from article content
            images = []
            if banner_image:
                images.append(banner_image)

            # Look for additional images in the content
            try:
                content_images = self.extract_images(article_soup, "https://news.blizzard.com")
                # Add unique images (excluding banner)
                for img in content_images:
                    if img != banner_image and img not in images:
                        images.append(img)
            except Exception as e:
                logger.warning(f"[DEBUG] Error extracting content images: {e}")

            # Limit total images
            images = images[:3]

            logger.info(f"[DEBUG] Extracted article:")
            logger.info(f"[DEBUG] - Title: {title}")
            logger.info(f"[DEBUG] - Content length: {len(content)}")
            logger.info(f"[DEBUG] - Images: {len(images)}")
            logger.info(f"[DEBUG] - Banner: {banner_image}")

            return NewsItem(
                title=title.strip(),
                content=content.strip(),
                images=images,
                website=self.website_name,
                destination_website=get_destination_website(self.website_name),
                theme=self.theme,
                url=article_url,
                published_date=datetime.now(),
                banner_image=banner_image
            )

        except Exception as e:
            logger.error(f"[DEBUG] Error extracting article data: {e}")
            return None
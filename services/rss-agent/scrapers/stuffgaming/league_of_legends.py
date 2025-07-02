from typing import List
from datetime import datetime
import re
from scrapers.base_scraper import BaseScraper
from models.schemas import NewsItem
from models.tracking import ScrapingTracker
from config.websites import get_destination_website
import logging

logger = logging.getLogger(__name__)


class LeagueOfLegendsScraper(BaseScraper):
    def __init__(self):
        super().__init__(
            base_url="https://www.leagueoflegends.com/fr-fr/news/",
            website_name="League of Legends",
            theme="Gaming"
        )
        # ✅ Ajouter le tracker
        self.tracker = ScrapingTracker()

    def scrape_news(self) -> List[NewsItem]:
        """Scrape League of Legends news - only new articles"""
        logger.info(f"[DEBUG] Starting scrape for {self.website_name}")

        try:
            soup = self.fetch_page(self.base_url)
            logger.info(f"[DEBUG] Successfully fetched main page: {self.base_url}")

            # Get last run time
            last_run = self.tracker.get_last_run("league_of_legends")
            logger.info(f"[DEBUG] Last run was: {last_run}")

            all_news_items = []

            # Extract all articles first
            article_links = soup.find_all('a',
                                          class_=['sc-985df63-0', 'cGQgsO', 'sc-d043b2-0', 'bZMlAb', 'sc-86f2e710-5',
                                                  'eFeRux', 'action'])

            logger.info(f"[DEBUG] Found {len(article_links)} article links with specific classes")

            # Fallback approach
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

            # Extract all articles
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

            # ✅ Filter for new articles only
            articles_data = [item.model_dump() for item in all_news_items]
            new_articles_data = self.tracker.filter_new_articles("league_of_legends", articles_data)

            logger.info(f"[DEBUG] New articles found: {len(new_articles_data)} out of {len(articles_data)}")

            # Convert back to NewsItem objects
            new_news_items = [NewsItem(**article_data) for article_data in new_articles_data]

            # ✅ Mark articles as seen (including the new ones)
            if articles_data:  # Mark all articles as seen, not just new ones
                self.tracker.mark_articles_as_seen("league_of_legends", articles_data)
                logger.info(f"[DEBUG] Marked {len(articles_data)} articles as seen")

            return new_news_items

        except Exception as e:
            logger.error(f"[DEBUG] Error in scrape_news: {e}")
            return []


    def _extract_article_data(self, link, index) -> NewsItem:
        """Extract data from a news link"""

        # Extract URL
        href = link.get('href', '')
        if href.startswith('/'):
            article_url = f"https://www.leagueoflegends.com{href}"
        elif href.startswith('http'):
            article_url = href
        else:
            article_url = f"https://www.leagueoflegends.com/fr-fr/news/{href}"

        # Extract title and basic info from link text
        link_text = link.get_text(strip=True)

        # Parse the link text
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

        logger.info(f"[DEBUG] Parsing link text: '{link_text[:100]}...'")
        logger.info(f"[DEBUG] Extracted - Category: '{category}', Date: '{date_str}', Title: '{title[:50]}...'")

        # Start with basic content
        content = description if description else "League of Legends news article"

        # Try to get full article content and images if it's an internal link
        images = []
        if article_url and article_url.startswith('https://www.leagueoflegends.com'):
            try:
                logger.info(f"[DEBUG] Fetching full article content from: {article_url}")
                article_soup = self.fetch_page(article_url)

                # Extract more detailed content
                full_content = self._extract_full_content(article_soup)
                if len(full_content) > len(content):
                    content = full_content

                # Extract images from full article
                images = self.extract_images(article_soup, "https://www.leagueoflegends.com")
                logger.info(f"[DEBUG] Extracted {len(images)} images from full article")

            except Exception as e:
                logger.warning(f"[DEBUG] Could not fetch full article content: {e}")

        # If no images found, try to extract from the main news page around this link
        if not images:
            try:
                # Look for images in the parent container
                parent = link.find_parent()
                if parent:
                    parent_images = self.extract_images(parent, "https://www.leagueoflegends.com")
                    images.extend(parent_images)
                    logger.info(f"[DEBUG] Extracted {len(parent_images)} images from parent container")
            except Exception as e:
                logger.warning(f"[DEBUG] Could not extract images from parent: {e}")

        # Parse date
        published_date = datetime.now()
        if date_str:
            try:
                published_date = datetime.strptime(date_str, "%d/%m/%Y")
            except Exception as e:
                logger.warning(f"[DEBUG] Could not parse date '{date_str}': {e}")

        # Remove duplicate images and limit
        images = list(dict.fromkeys(images))[:3]

        logger.info(
            f"[DEBUG] Final article - Title: {title[:50]}, Images: {len(images)}, Content length: {len(content)}, URL: {article_url}")

        return NewsItem(
            title=title.strip(),
            content=content.strip()[:2000],
            images=images,
            website=self.website_name,
            destination_website=get_destination_website(self.website_name),  # Utilise la config
            theme=self.theme,
            url=article_url,
            published_date=published_date
        )

    def _extract_full_content(self, soup) -> str:
        """Extract full content from article page"""
        content_selectors = [
            'article',
            '[role="main"]',
            '.content',
            '.article-content',
            '.post-content',
            '.news-content',
            'main',
            '[class*="content"]',
            '[class*="article"]',
            'div[class*="sc-"]',  # styled-components
            'div[class*="text"]',
            'div[class*="body"]',
            'p'
        ]

        content_parts = []

        for selector in content_selectors:
            elements = soup.select(selector)
            for element in elements:
                if element:
                    # Remove unwanted elements
                    for unwanted in element(["script", "style", "nav", "footer", "header", "aside"]):
                        unwanted.decompose()

                    text = element.get_text(separator=' ', strip=True)
                    if len(text) > 50 and text not in content_parts:
                        content_parts.append(text)

        full_content = ' '.join(content_parts)
        full_content = re.sub(r'\s+', ' ', full_content).strip()

        return full_content[:2000] if full_content else ""
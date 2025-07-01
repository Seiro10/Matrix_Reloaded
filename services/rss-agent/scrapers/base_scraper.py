from abc import ABC, abstractmethod
from typing import List
import requests
from bs4 import BeautifulSoup
from models.schemas import NewsItem
import logging

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    def __init__(self, base_url: str, website_name: str, theme: str):
        self.base_url = base_url
        self.website_name = website_name
        self.theme = theme
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    @abstractmethod
    def scrape_news(self) -> List[NewsItem]:
        """Scrape news from the website and return list of NewsItem"""
        pass

    def fetch_page(self, url: str) -> BeautifulSoup:
        """Fetch and parse a webpage"""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return BeautifulSoup(response.content, 'html.parser')
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            raise

    def extract_images(self, soup: BeautifulSoup, base_url: str = None) -> List[str]:
        """Extract image URLs from soup with better filtering"""
        images = []

        # Look for various image attributes
        img_attributes = ['src', 'data-src', 'data-lazy-src', 'data-original', 'data-srcset']

        img_tags = soup.find_all('img')

        for img in img_tags:
            src = None

            # Try different attributes
            for attr in img_attributes:
                src = img.get(attr)
                if src:
                    break

            if src:
                # Clean up srcset (take first URL)
                if ',' in src:
                    src = src.split(',')[0].strip().split(' ')[0]

                # Build full URL
                if src.startswith('http'):
                    images.append(src)
                elif base_url and src.startswith('/'):
                    images.append(f"{base_url.rstrip('/')}{src}")
                elif base_url and not src.startswith('http'):
                    images.append(f"{base_url.rstrip('/')}/{src}")

        # Filter out small icons, ads, etc.
        filtered_images = []
        for img_url in images:
            if self._is_valid_image(img_url):
                filtered_images.append(img_url)

        # Remove duplicates while preserving order
        seen = set()
        unique_images = []
        for img in filtered_images:
            if img not in seen:
                seen.add(img)
                unique_images.append(img)

        logger.info(f"[DEBUG] Extracted {len(unique_images)} valid images from {len(img_tags)} img tags")
        return unique_images

    def _is_valid_image(self, img_url: str) -> bool:
        """Check if image URL is valid for content"""
        # Skip tiny images, icons, ads
        skip_keywords = [
            'icon', 'logo', 'avatar', 'thumb', 'ad', 'banner',
            'pixel', 'tracking', 'analytics', 'social', 'share',
            '16x16', '32x32', '64x64', '1x1'
        ]

        img_url_lower = img_url.lower()

        # Skip if contains skip keywords
        if any(keyword in img_url_lower for keyword in skip_keywords):
            return False

        # Skip if looks like a tiny image
        if any(size in img_url_lower for size in ['16x16', '32x32', '1x1', '2x2']):
            return False

        # Must be common image format
        valid_extensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif']
        if not any(ext in img_url_lower for ext in valid_extensions):
            # Check if URL has query params that might indicate an image
            if '?' not in img_url:
                return False

        return True
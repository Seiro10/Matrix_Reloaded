from abc import ABC, abstractmethod
from typing import List, Optional
import requests
from bs4 import BeautifulSoup
from models.schemas import NewsItem
import logging

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    def __init__(self, base_url: str, website_name: str, theme: str, use_playwright: bool = False):
        self.base_url = base_url
        self.website_name = website_name
        self.theme = theme
        self.use_playwright = use_playwright

        # Always initialize session (needed for fallback)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })

    @abstractmethod
    def scrape_news(self) -> List[NewsItem]:
        """Scrape news from the website and return list of NewsItem"""
        pass

    def fetch_page(self, url: str) -> BeautifulSoup:
        """Fetch and parse a webpage - with Playwright support for JS-rendered content"""
        if self.use_playwright:
            return self._fetch_page_playwright(url)
        else:
            return self._fetch_page_requests(url)

    def _fetch_page_requests(self, url: str) -> BeautifulSoup:
        """Fetch page using requests (for static content)"""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return BeautifulSoup(response.content, 'html.parser')
        except Exception as e:
            logger.error(f"Error fetching {url} with requests: {e}")
            raise

    def _fetch_page_playwright(self, url: str) -> BeautifulSoup:
        """Fetch page using Playwright (for JS-rendered content)"""
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()

                # Set a realistic user agent
                page.set_extra_http_headers({
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                })

                # Navigate and wait for content to load - INCREASE TIMEOUT
                page.goto(url, wait_until='networkidle', timeout=60000)  # Increased from 30s to 60s

                # Wait a bit more for any lazy-loaded content
                page.wait_for_timeout(3000)  # Increased from 2s to 3s

                # Get the final HTML after JS execution
                html = page.content()
                browser.close()

                logger.info(f"[DEBUG] Successfully fetched JS-rendered page: {url}")
                return BeautifulSoup(html, 'html.parser')

        except Exception as e:
            logger.error(f"Error fetching {url} with Playwright: {e}")
            # Fallback to requests if Playwright fails
            logger.info(f"[DEBUG] Falling back to requests for {url}")
            return self._fetch_page_requests(url)


    def extract_images(self, soup: BeautifulSoup, base_url: str = None) -> List[str]:
        """Extract image URLs from soup with better filtering"""
        images = []

        # Look for various image attributes including modern formats
        img_attributes = [
            'src', 'data-src', 'data-lazy-src', 'data-original',
            'data-srcset', 'srcset', 'data-lazy', 'data-image',
            'data-bg', 'data-background-image'
        ]

        img_tags = soup.find_all('img')

        for img in img_tags:
            src = None

            # Try different attributes in order of preference
            for attr in img_attributes:
                potential_src = img.get(attr)
                if potential_src and not potential_src.startswith('data:'):
                    src = potential_src
                    break

            # Skip if no valid src found
            if not src:
                continue

            # Handle srcset (take the largest image)
            if 'srcset' in src or ',' in src:
                src_parts = src.split(',')
                # Take the last one (usually highest resolution)
                src = src_parts[-1].strip().split(' ')[0]

            # Build full URL
            if src.startswith('http'):
                full_url = src
            elif base_url and src.startswith('/'):
                full_url = f"{base_url.rstrip('/')}{src}"
            elif base_url and src.startswith('./'):
                full_url = f"{base_url.rstrip('/')}/{src[2:]}"
            elif base_url and not src.startswith('http'):
                full_url = f"{base_url.rstrip('/')}/{src}"
            else:
                continue

            # Validate before adding
            if self._is_valid_image(full_url):
                images.append(full_url)

        # Also look for background images in style attributes
        for element in soup.find_all(['div', 'section', 'header'], style=True):
            style = element.get('style', '')
            if 'background-image:' in style:
                import re
                bg_match = re.search(r'background-image:\s*url\(["\']?([^"\']+)["\']?\)', style)
                if bg_match:
                    bg_url = bg_match.group(1)
                    if not bg_url.startswith('data:'):
                        if bg_url.startswith('http'):
                            full_url = bg_url
                        elif base_url and bg_url.startswith('/'):
                            full_url = f"{base_url.rstrip('/')}{bg_url}"
                        else:
                            continue

                        if self._is_valid_image(full_url):
                            images.append(full_url)

        # Remove duplicates while preserving order
        seen = set()
        unique_images = []
        for img in images:
            if img not in seen:
                seen.add(img)
                unique_images.append(img)

        logger.info(f"[DEBUG] Extracted {len(unique_images)} valid images from {len(img_tags)} img tags")
        return unique_images

    def _is_valid_image(self, img_url: str) -> bool:
        """Check if image URL is valid for content"""
        # Skip data URIs and placeholder images
        if img_url.startswith('data:'):
            return False

        # Skip empty SVG placeholders
        if 'svg+xml' in img_url.lower() and ('xmlns' in img_url or 'svg' in img_url):
            return False

        # Skip tiny images, icons, ads
        skip_keywords = [
            'icon', 'logo', 'avatar', 'thumb', 'ad', 'banner',
            'pixel', 'tracking', 'analytics', 'social', 'share',
            '16x16', '32x32', '64x64', '1x1', 'spacer', 'placeholder'
        ]

        img_url_lower = img_url.lower()

        # Skip if contains skip keywords
        if any(keyword in img_url_lower for keyword in skip_keywords):
            return False

        # Skip if looks like a tiny image
        if any(size in img_url_lower for size in ['16x16', '32x32', '1x1', '2x2']):
            return False

        # Must be common image format (including modern formats)
        valid_extensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.avif', '.svg']
        has_valid_ext = any(ext in img_url_lower for ext in valid_extensions)

        # If no extension, check if URL has query params that might indicate an image
        if not has_valid_ext and '?' not in img_url:
            return False

        # Must be a proper HTTP/HTTPS URL
        if not img_url.startswith(('http://', 'https://')):
            return False

        return True

    def extract_banner_image(self, soup: BeautifulSoup, banner_selectors: List[str], base_url: str = None) -> Optional[
        str]:
        """Extract banner image using stable selectors - with debugging"""

        # Strategy 1: Use data-testid (most reliable for modern websites)
        banner_img = soup.find('img', {'data-testid': 'banner-image'})
        if banner_img:
            src = self._extract_image_src(banner_img)
            if src:
                full_url = self._build_full_url(src, base_url)
                if full_url and self._is_valid_image(full_url):
                    logger.info(f"[DEBUG] Found banner image using data-testid: {full_url}")
                    return full_url

        # Strategy 2: Look for other banner-related data-testid
        banner_testids = ['hero-image', 'featured-image', 'main-image', 'header-image']
        for testid in banner_testids:
            banner_img = soup.find('img', {'data-testid': testid})
            if banner_img:
                src = self._extract_image_src(banner_img)
                if src:
                    full_url = self._build_full_url(src, base_url)
                    if full_url and self._is_valid_image(full_url):
                        logger.info(f"[DEBUG] Found banner image using data-testid='{testid}': {full_url}")
                        return full_url

        # Strategy 3: Use custom selectors as final fallback
        for selector in banner_selectors:
            try:
                banner_img = soup.select_one(selector)
                if banner_img:
                    src = self._extract_image_src(banner_img)
                    if src:
                        full_url = self._build_full_url(src, base_url)
                        if full_url and self._is_valid_image(full_url):
                            logger.info(f"[DEBUG] Found banner image using custom selector '{selector}': {full_url}")
                            return full_url
            except Exception as e:
                logger.warning(f"[DEBUG] Error with custom selector '{selector}': {e}")
                continue

        logger.warning("[DEBUG] No valid banner image found with any strategy")
        return None


    def _extract_image_src(self, img_tag) -> Optional[str]:
        """Extract src from img tag trying multiple attributes"""
        if not img_tag:
            return None

        # Try different attributes in order of preference
        for attr in ['src', 'data-src', 'data-lazy-src', 'data-original']:
            src = img_tag.get(attr)
            if src and not src.startswith('data:') and len(src) > 10:
                # Handle srcset
                if ',' in src:
                    src_parts = src.split(',')
                    src = src_parts[-1].strip().split(' ')[0]
                return src

        return None

    def _build_full_url(self, src: str, base_url: str = None) -> Optional[str]:
        """Build full URL from src and base_url"""
        if not src:
            return None

        if src.startswith('http'):
            return src
        elif base_url and src.startswith('/'):
            return f"{base_url.rstrip('/')}{src}"
        elif base_url and not src.startswith('http'):
            return f"{base_url.rstrip('/')}/{src}"

        return None

    def extract_images_with_banner(self, soup: BeautifulSoup, banner_selectors: List[str], base_url: str = None) -> \
    tuple[Optional[str], List[str]]:
        """Extract banner image separately from other images"""
        # Extract banner image first
        banner_image = self.extract_banner_image(soup, banner_selectors, base_url)

        # Extract all images
        all_images = self.extract_images(soup, base_url)

        # Remove banner image from all images if found
        other_images = []
        if banner_image:
            other_images = [img for img in all_images if img != banner_image]
        else:
            other_images = all_images

        return banner_image, other_images
import requests
import logging
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse, urljoin
from datetime import datetime
import time
import json

from .models import ArticleContent, WordPressResponse
from .config import WORDPRESS_CONFIG

logger = logging.getLogger(__name__)


class WordPressAPIError(Exception):
    """Custom exception for WordPress API errors"""

    def __init__(self, message: str, status_code: Optional[int] = None, response_data: Optional[Dict] = None):
        self.message = message
        self.status_code = status_code
        self.response_data = response_data
        super().__init__(self.message)


class WordPressAPI:
    """WordPress REST API client with JWT authentication"""

    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize WordPress API client

        Args:
            config: Optional configuration dict, uses WORDPRESS_CONFIG if None
        """
        self.config = config or WORDPRESS_CONFIG
        self.base_url = self.config['api_url'].rstrip('/')
        self.username = self.config['username']
        self.password = self.config['password']
        self.timeout = self.config.get('timeout', 30)
        self.retry_attempts = self.config.get('retry_attempts', 3)

        self.token = None
        self.token_expires_at = None
        self.session = requests.Session()

        # Set default headers
        self.session.headers.update({
            'User-Agent': 'Rewriter-Agent/1.0.0',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })

        logger.info(f"🔧 WordPress API client initialized for {self.base_url}")

    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """
        Make HTTP request with retry logic

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint
            **kwargs: Additional arguments for requests

        Returns:
            requests.Response object

        Raises:
            WordPressAPIError: If request fails after retries
        """
        url = urljoin(self.base_url, endpoint.lstrip('/'))
        kwargs.setdefault('timeout', self.timeout)

        last_exception = None

        for attempt in range(self.retry_attempts):
            try:
                logger.debug(f"🔄 {method} {url} (attempt {attempt + 1})")
                response = self.session.request(method, url, **kwargs)

                # Log response details
                logger.debug(f"📊 Response: {response.status_code} ({len(response.content)} bytes)")

                return response

            except requests.exceptions.RequestException as e:
                last_exception = e
                logger.warning(f"⚠️ Request attempt {attempt + 1} failed: {e}")

                if attempt < self.retry_attempts - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.info(f"⏳ Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)

        # All attempts failed
        raise WordPressAPIError(
            f"Request failed after {self.retry_attempts} attempts: {last_exception}",
            response_data={'last_error': str(last_exception)}
        )

    def authenticate(self) -> bool:
        """
        Authenticate with WordPress using JWT

        Returns:
            bool: True if authentication successful

        Raises:
            WordPressAPIError: If authentication fails
        """
        auth_endpoint = "/jwt-auth/v1/token"
        auth_data = {
            "username": self.username,
            "password": self.password
        }

        try:
            logger.info("🔐 Authenticating with WordPress...")
            response = self._make_request('POST', auth_endpoint, json=auth_data)

            if response.status_code == 200:
                data = response.json()
                self.token = data.get('token')

                if self.token:
                    # Update session headers with token
                    self.session.headers['Authorization'] = f'Bearer {self.token}'

                    # Set token expiration (24 hours from now as default)
                    self.token_expires_at = datetime.now().timestamp() + (24 * 3600)

                    logger.info("✅ WordPress authentication successful")
                    return True
                else:
                    raise WordPressAPIError("No token received in authentication response")
            else:
                error_data = response.json() if response.content else {}
                raise WordPressAPIError(
                    f"Authentication failed: {error_data.get('message', 'Unknown error')}",
                    status_code=response.status_code,
                    response_data=error_data
                )

        except requests.exceptions.JSONDecodeError:
            raise WordPressAPIError("Invalid JSON response from authentication endpoint")
        except Exception as e:
            if isinstance(e, WordPressAPIError):
                raise
            raise WordPressAPIError(f"Authentication error: {str(e)}")

    def _ensure_authenticated(self):
        """Ensure we have a valid authentication token"""
        if not self.token or (self.token_expires_at and datetime.now().timestamp() > self.token_expires_at):
            logger.info("🔄 Token expired or missing, re-authenticating...")
            self.authenticate()

    def get_article_by_url(self, article_url: str) -> Optional[ArticleContent]:
        """
        Fetch article content by URL

        Args:
            article_url: Full URL of the WordPress article

        Returns:
            ArticleContent object if found, None otherwise

        Raises:
            WordPressAPIError: If API request fails
        """
        self._ensure_authenticated()

        try:
            # Extract slug from URL
            parsed_url = urlparse(article_url)
            path_parts = [part for part in parsed_url.path.strip('/').split('/') if part]
            slug = path_parts[-1] if path_parts else None

            if not slug:
                raise WordPressAPIError(f"Could not extract slug from URL: {article_url}")

            logger.info(f"🔍 Fetching article with slug: {slug}")

            # Search for post by slug
            search_endpoint = "/wp/v2/posts"
            params = {
                'slug': slug,
                'per_page': 1,
                '_embed': True  # Include embedded data (featured media, tags, etc.)
            }

            response = self._make_request('GET', search_endpoint, params=params)

            if response.status_code == 200:
                posts = response.json()

                if not posts:
                    logger.warning(f"⚠️ No article found for slug: {slug}")
                    return None

                post = posts[0]

                # Extract embedded data
                embedded = post.get('_embedded', {})

                # Get tags and categories
                terms = embedded.get('wp:term', [])
                tags = []
                categories = []

                if terms:
                    # Tags are usually in terms[1], categories in terms[0]
                    if len(terms) > 0 and isinstance(terms[0], list):
                        categories = [cat.get('name', '') for cat in terms[0]]
                    if len(terms) > 1 and isinstance(terms[1], list):
                        tags = [tag.get('name', '') for tag in terms[1]]

                # Get featured image
                featured_media = embedded.get('wp:featuredmedia', [])
                featured_image = None
                if featured_media and len(featured_media) > 0:
                    featured_image = featured_media[0].get('source_url')

                # Create ArticleContent object
                article = ArticleContent(
                    id=post['id'],
                    title=post['title']['rendered'],
                    content=post['content']['rendered'],
                    slug=post['slug'],
                    meta_description=post.get('excerpt', {}).get('rendered', '').strip(),
                    featured_image=featured_image,
                    tags=tags,
                    categories=categories,
                    status=post.get('status', 'publish'),
                    author_id=post.get('author'),
                    published_date=datetime.fromisoformat(post['date'].replace('Z', '+00:00')) if post.get(
                        'date') else None,
                    modified_date=datetime.fromisoformat(post['modified'].replace('Z', '+00:00')) if post.get(
                        'modified') else None
                )

                logger.info(f"✅ Successfully fetched article: {article.title}")
                return article

            else:
                error_data = response.json() if response.content else {}
                raise WordPressAPIError(
                    f"Failed to fetch article: {error_data.get('message', 'Unknown error')}",
                    status_code=response.status_code,
                    response_data=error_data
                )

        except Exception as e:
            if isinstance(e, WordPressAPIError):
                raise
            logger.error(f"❌ Error fetching article: {e}")
            raise WordPressAPIError(f"Error fetching article: {str(e)}")

    def get_article_by_id(self, post_id: int) -> Optional[ArticleContent]:
        """
        Fetch article content by post ID

        Args:
            post_id: WordPress post ID

        Returns:
            ArticleContent object if found, None otherwise
        """
        self._ensure_authenticated()

        try:
            logger.info(f"🔍 Fetching article with ID: {post_id}")

            endpoint = f"/wp/v2/posts/{post_id}"
            params = {'_embed': True}

            response = self._make_request('GET', endpoint, params=params)

            if response.status_code == 200:
                post = response.json()

                # Convert to ArticleContent (similar to get_article_by_url)
                embedded = post.get('_embedded', {})
                terms = embedded.get('wp:term', [])

                tags = []
                categories = []
                if terms:
                    if len(terms) > 0 and isinstance(terms[0], list):
                        categories = [cat.get('name', '') for cat in terms[0]]
                    if len(terms) > 1 and isinstance(terms[1], list):
                        tags = [tag.get('name', '') for tag in terms[1]]

                featured_media = embedded.get('wp:featuredmedia', [])
                featured_image = None
                if featured_media and len(featured_media) > 0:
                    featured_image = featured_media[0].get('source_url')

                article = ArticleContent(
                    id=post['id'],
                    title=post['title']['rendered'],
                    content=post['content']['rendered'],
                    slug=post['slug'],
                    meta_description=post.get('excerpt', {}).get('rendered', '').strip(),
                    featured_image=featured_image,
                    tags=tags,
                    categories=categories,
                    status=post.get('status', 'publish'),
                    author_id=post.get('author'),
                    published_date=datetime.fromisoformat(post['date'].replace('Z', '+00:00')) if post.get(
                        'date') else None,
                    modified_date=datetime.fromisoformat(post['modified'].replace('Z', '+00:00')) if post.get(
                        'modified') else None
                )

                logger.info(f"✅ Successfully fetched article: {article.title}")
                return article

            elif response.status_code == 404:
                logger.warning(f"⚠️ Article with ID {post_id} not found")
                return None
            else:
                error_data = response.json() if response.content else {}
                raise WordPressAPIError(
                    f"Failed to fetch article: {error_data.get('message', 'Unknown error')}",
                    status_code=response.status_code,
                    response_data=error_data
                )

        except Exception as e:
            if isinstance(e, WordPressAPIError):
                raise
            logger.error(f"❌ Error fetching article by ID: {e}")
            raise WordPressAPIError(f"Error fetching article: {str(e)}")

    def update_article(
            self,
            article_id: int,
            updated_content: str,
            title: Optional[str] = None,
            status: str = "private",
            meta_description: Optional[str] = None
    ) -> WordPressResponse:
        """
        Update article content via WordPress API

        Args:
            article_id: WordPress post ID
            updated_content: New HTML content
            title: Optional new title
            status: Post status (private, draft, publish)
            meta_description: Optional new meta description

        Returns:
            WordPressResponse with update results

        Raises:
            WordPressAPIError: If update fails
        """
        self._ensure_authenticated()

        try:
            logger.info(f"🔄 Updating article {article_id} (status: {status})")

            endpoint = f"/wp/v2/posts/{article_id}"

            # Prepare update payload
            payload = {
                "content": updated_content,
                "status": status
            }

            if title:
                payload["title"] = title

            if meta_description:
                payload["excerpt"] = meta_description

            # Add metadata about the update
            payload["meta"] = {
                "rewriter_agent_updated": datetime.now().isoformat(),
                "rewriter_agent_version": "1.0.0"
            }

            response = self._make_request('POST', endpoint, json=payload)

            if response.status_code == 200:
                updated_post = response.json()

                logger.info(f"✅ Article {article_id} updated successfully")

                return WordPressResponse(
                    success=True,
                    post_id=updated_post['id'],
                    message=f"Article updated successfully (status: {status})",
                    status_code=response.status_code,
                    response_data={
                        'title': updated_post['title']['rendered'],
                        'status': updated_post['status'],
                        'modified': updated_post['modified'],
                        'link': updated_post['link']
                    }
                )
            else:
                error_data = response.json() if response.content else {}
                error_message = error_data.get('message', 'Unknown error')

                logger.error(f"❌ Failed to update article {article_id}: {error_message}")

                return WordPressResponse(
                    success=False,
                    post_id=article_id,
                    message=f"Update failed: {error_message}",
                    status_code=response.status_code,
                    response_data=error_data
                )

        except Exception as e:
            if isinstance(e, WordPressAPIError):
                raise
            logger.error(f"❌ Error updating article: {e}")
            raise WordPressAPIError(f"Error updating article: {str(e)}")

    def create_backup(self, article_id: int) -> Dict[str, Any]:
        """
        Create a backup of article before updating

        Args:
            article_id: WordPress post ID

        Returns:
            Dict with backup data
        """
        try:
            article = self.get_article_by_id(article_id)
            if not article:
                raise WordPressAPIError(f"Article {article_id} not found for backup")

            backup_data = {
                'timestamp': datetime.now().isoformat(),
                'article_id': article_id,
                'original_title': article.title,
                'original_content': article.content,
                'original_status': article.status,
                'original_modified': article.modified_date.isoformat() if article.modified_date else None
            }

            logger.info(f"📦 Created backup for article {article_id}")
            return backup_data

        except Exception as e:
            logger.error(f"❌ Error creating backup: {e}")
            raise

    def verify_connection(self) -> bool:
        """
        Verify WordPress API connection and authentication

        Returns:
            bool: True if connection is working
        """
        try:
            # Test authentication
            self.authenticate()

            # Test API access with a simple request
            response = self._make_request('GET', '/wp/v2/users/me')

            if response.status_code == 200:
                user_data = response.json()
                logger.info(f"✅ WordPress connection verified for user: {user_data.get('name', 'Unknown')}")
                return True
            else:
                logger.error(f"❌ WordPress connection failed: HTTP {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"❌ WordPress connection verification failed: {e}")
            return False

    def get_site_info(self) -> Dict[str, Any]:
        """
        Get WordPress site information

        Returns:
            Dict with site information
        """
        try:
            response = self._make_request('GET', '/')

            if response.status_code == 200:
                site_data = response.json()
                return {
                    'name': site_data.get('name', 'Unknown'),
                    'description': site_data.get('description', ''),
                    'url': site_data.get('url', ''),
                    'gmt_offset': site_data.get('gmt_offset', 0),
                    'timezone_string': site_data.get('timezone_string', ''),
                    'namespaces': site_data.get('namespaces', [])
                }
            else:
                return {'error': f'Failed to fetch site info: HTTP {response.status_code}'}

        except Exception as e:
            logger.error(f"❌ Error fetching site info: {e}")
            return {'error': str(e)}

    def search_articles(self, search_term: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search for articles by term

        Args:
            search_term: Search term
            limit: Maximum number of results

        Returns:
            List of article summaries
        """
        self._ensure_authenticated()

        try:
            params = {
                'search': search_term,
                'per_page': min(limit, 100),
                'status': 'publish'
            }

            response = self._make_request('GET', '/wp/v2/posts', params=params)

            if response.status_code == 200:
                posts = response.json()

                results = []
                for post in posts:
                    results.append({
                        'id': post['id'],
                        'title': post['title']['rendered'],
                        'slug': post['slug'],
                        'link': post['link'],
                        'excerpt': post['excerpt']['rendered'],
                        'date': post['date']
                    })

                logger.info(f"🔍 Found {len(results)} articles for search: {search_term}")
                return results
            else:
                logger.error(f"❌ Search failed: HTTP {response.status_code}")
                return []

        except Exception as e:
            logger.error(f"❌ Error searching articles: {e}")
            return []

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup session"""
        if hasattr(self, 'session'):
            self.session.close()


# Utility functions
def create_wordpress_client(config: Dict[str, Any] = None) -> WordPressAPI:
    """
    Factory function to create WordPress API client

    Args:
        config: Optional configuration dict

    Returns:
        WordPressAPI instance
    """
    return WordPressAPI(config)


def test_wordpress_connection(config: Dict[str, Any] = None) -> bool:
    """
    Test WordPress API connection

    Args:
        config: Optional configuration dict

    Returns:
        bool: True if connection successful
    """
    try:
        with create_wordpress_client(config) as wp_client:
            return wp_client.verify_connection()
    except Exception as e:
        logger.error(f"❌ WordPress connection test failed: {e}")
        return False


# Export main classes and functions
__all__ = [
    'WordPressAPI',
    'WordPressAPIError',
    'create_wordpress_client',
    'test_wordpress_connection'
]
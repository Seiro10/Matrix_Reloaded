import boto3
import requests
from config.settings import settings
import logging
from typing import Optional
import mimetypes
from urllib.parse import urlparse
import os

logger = logging.getLogger(__name__)


class S3Service:
    def __init__(self):
        # Debug AWS credentials
        logger.info(f"[DEBUG] AWS_ACCESS_KEY_ID: {settings.aws_access_key_id[:10]}..." if settings.aws_access_key_id else "[DEBUG] AWS_ACCESS_KEY_ID: EMPTY")
        logger.info(f"[DEBUG] AWS_SECRET_ACCESS_KEY: {'SET' if settings.aws_secret_access_key else 'EMPTY'}")
        logger.info(f"[DEBUG] S3_BUCKET_NAME: {settings.s3_bucket_name}")
        logger.info(f"[DEBUG] S3_REGION: {settings.s3_region}")

        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.s3_region
        )
        self.bucket_name = settings.s3_bucket_name

    async def upload_image_from_url(self, image_url: str, s3_key: str) -> Optional[str]:
        """Download image from URL and upload to S3"""
        try:
            logger.info(f"[DEBUG] Downloading image: {image_url}")

            # Download image with better headers
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Accept-Language': 'en-US,en;q=0.9',
                'Cache-Control': 'no-cache'
            }

            response = requests.get(image_url, timeout=15, headers=headers)
            response.raise_for_status()

            logger.info(
                f"[DEBUG] Downloaded image - Status: {response.status_code}, Size: {len(response.content)} bytes")

            # Detect content type from response
            content_type = response.headers.get('content-type', '')
            logger.info(f"[DEBUG] Image content-type: {content_type}")

            # Determine file extension from content type or URL
            file_extension = self._get_file_extension(image_url, content_type)
            logger.info(f"[DEBUG] Detected file extension: {file_extension}")

            # Update S3 key with correct extension
            s3_key_parts = s3_key.rsplit('.', 1)
            if len(s3_key_parts) == 2:
                s3_key = f"{s3_key_parts[0]}{file_extension}"
            else:
                s3_key = f"{s3_key}{file_extension}"

            logger.info(f"[DEBUG] Updated S3 key: {s3_key}")

            # Map content type for S3
            s3_content_type = self._get_s3_content_type(file_extension, content_type)

            # Upload to S3
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=response.content,
                ContentType=s3_content_type,
                CacheControl='max-age=31536000',  # 1 year cache
                Metadata={
                    'original-url': image_url,
                    'original-content-type': content_type
                }
            )

            s3_url = f"https://{self.bucket_name}.s3.{settings.s3_region}.amazonaws.com/{s3_key}"
            logger.info(f"[DEBUG] Image uploaded to S3: {s3_url}")
            return s3_url

        except requests.exceptions.RequestException as e:
            logger.error(f"[DEBUG] Error downloading image from {image_url}: {e}")
            return None
        except Exception as e:
            logger.error(f"[DEBUG] Error uploading image to S3: {e}")
            return None

    def _get_file_extension(self, image_url: str, content_type: str) -> str:
        """Determine the correct file extension"""

        # Map content types to extensions
        content_type_map = {
            'image/avif': '.avif',
            'image/webp': '.webp',
            'image/jpeg': '.jpg',
            'image/jpg': '.jpg',
            'image/png': '.png',
            'image/gif': '.gif',
            'image/svg+xml': '.svg',
            'image/bmp': '.bmp',
            'image/tiff': '.tiff'
        }

        # First try content type
        if content_type in content_type_map:
            return content_type_map[content_type]

        # Then try URL extension
        parsed_url = urlparse(image_url)
        path = parsed_url.path.lower()

        if '.avif' in path:
            return '.avif'
        elif '.webp' in path:
            return '.webp'
        elif '.jpg' in path or '.jpeg' in path:
            return '.jpg'
        elif '.png' in path:
            return '.png'
        elif '.gif' in path:
            return '.gif'
        elif '.svg' in path:
            return '.svg'

        # Default fallback
        return '.jpg'

    def _get_s3_content_type(self, file_extension: str, original_content_type: str) -> str:
        """Get the appropriate content type for S3"""

        extension_map = {
            '.avif': 'image/avif',
            '.webp': 'image/webp',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.svg': 'image/svg+xml',
            '.bmp': 'image/bmp',
            '.tiff': 'image/tiff'
        }

        # Use extension mapping first
        if file_extension in extension_map:
            return extension_map[file_extension]

        # Fall back to original content type if available
        if original_content_type.startswith('image/'):
            return original_content_type

        # Default
        return 'image/jpeg'
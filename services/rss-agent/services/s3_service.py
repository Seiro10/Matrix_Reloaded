import boto3
import requests
from config.settings import settings
import logging
from typing import Optional
import mimetypes
from urllib.parse import urlparse
import os
from dotenv import load_dotenv
from PIL import Image
import io

logger = logging.getLogger(__name__)


class S3Service:
    def __init__(self):
        import os

        # Read directly from environment - bypass settings completely
        aws_access_key_id = None
        aws_secret_access_key = None

        # Try multiple ways to get credentials
        for key_name in ['AWS_ACCESS_KEY_ID', 'aws_access_key_id']:
            if key_name in os.environ:
                aws_access_key_id = os.environ[key_name]
                break

        for key_name in ['AWS_SECRET_ACCESS_KEY', 'aws_secret_access_key']:
            if key_name in os.environ:
                aws_secret_access_key = os.environ[key_name]
                break

        # If still empty, read from parent process environment
        if not aws_access_key_id:
            try:
                with open('/proc/1/environ', 'rb') as f:
                    env_data = f.read().decode('utf-8', errors='ignore')
                    for line in env_data.split('\x00'):
                        if line.startswith('AWS_ACCESS_KEY_ID='):
                            aws_access_key_id = line.split('=', 1)[1]
                        elif line.startswith('AWS_SECRET_ACCESS_KEY='):
                            aws_secret_access_key = line.split('=', 1)[1]
            except:
                pass

        # REMOVE THE HARDCODED FALLBACK - REPLACE WITH ERROR
        if not aws_access_key_id or not aws_secret_access_key:
            logger.error("[DEBUG] AWS credentials not found in environment")
            self.s3_client = None
            self.bucket_name = "matrix-reloaded-rss-img-bucket"
            return

        s3_bucket_name = "matrix-reloaded-rss-img-bucket"
        s3_region = "eu-west-3"

        # Debug credentials (without showing actual values)
        logger.info(f"[DEBUG] AWS_ACCESS_KEY_ID: {aws_access_key_id[:10]}...")
        logger.info(f"[DEBUG] AWS_SECRET_ACCESS_KEY: {'SET' if aws_secret_access_key else 'EMPTY'}")
        logger.info(f"[DEBUG] S3_BUCKET_NAME: {s3_bucket_name}")
        logger.info(f"[DEBUG] S3_REGION: {s3_region}")

        try:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
                region_name=s3_region
            )
            self.bucket_name = s3_bucket_name

            logger.info(f"[DEBUG] ✅ S3 client initialized successfully")

        except Exception as e:
            logger.error(f"[DEBUG] ❌ Failed to initialize S3 client: {e}")
            self.s3_client = None

    def _sanitize_s3_key(self, s3_key: str) -> str:
        """Sanitize S3 key to remove problematic characters"""
        import re

        # Remove or replace problematic characters with underscore
        sanitized = re.sub(r'[^\w\-_./]', '_', s3_key)
        # Remove multiple underscores
        sanitized = re.sub(r'_+', '_', sanitized)
        # Remove leading/trailing underscores from each path segment
        parts = sanitized.split('/')
        parts = [part.strip('_') for part in parts if part.strip('_')]
        sanitized = '/'.join(parts)

        return sanitized

    async def upload_image_from_url(self, image_url: str, s3_key: str, convert_to_jpg: bool = True) -> Optional[str]:
        """Download image from URL, optionally convert to JPG, and upload to S3"""
        try:
            # Validate URL before attempting download
            if not self._is_valid_image_url(image_url):
                logger.warning(f"[DEBUG] Invalid image URL rejected: {image_url}")
                return None

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

            # Process the image
            if convert_to_jpg:
                image_data, final_content_type, final_extension = self._convert_to_jpg(response.content, content_type)
                if not image_data:
                    logger.error(f"[DEBUG] Failed to convert image to JPG: {image_url}")
                    # Fallback: upload original image
                    logger.info(f"[DEBUG] Uploading original image instead")
                    image_data = response.content
                    final_extension = self._get_file_extension(image_url, content_type)
                    final_content_type = self._get_s3_content_type(final_extension, content_type)
            else:
                image_data = response.content
                final_extension = self._get_file_extension(image_url, content_type)
                final_content_type = self._get_s3_content_type(final_extension, content_type)

            # Update S3 key with correct extension
            s3_key_parts = s3_key.rsplit('.', 1)
            if len(s3_key_parts) == 2:
                s3_key = f"{s3_key_parts[0]}{final_extension}"
            else:
                s3_key = f"{s3_key}{final_extension}"

            # Sanitize the S3 key
            s3_key = self._sanitize_s3_key(s3_key)
            logger.info(f"[DEBUG] Final S3 key: {s3_key}")

            # Check if S3 client is available
            if not self.s3_client:
                logger.error("[DEBUG] S3 client not initialized - cannot upload")
                return None

            # Upload to S3
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=image_data,
                ContentType=final_content_type,
                CacheControl='max-age=31536000',  # 1 year cache
                Metadata={
                    'original-url': image_url,
                    'original-content-type': content_type,
                    'converted': str(convert_to_jpg and final_extension == '.jpg')
                }
            )

            s3_url = f"https://{self.bucket_name}.s3.eu-west-3.amazonaws.com/{s3_key}"
            logger.info(f"[DEBUG] Image uploaded to S3: {s3_url}")
            return s3_url

        except requests.exceptions.RequestException as e:
            logger.error(f"[DEBUG] Error downloading image from {image_url}: {e}")
            return None
        except Exception as e:
            logger.error(f"[DEBUG] Error uploading image to S3: {e}")
            return None

    def _convert_to_jpg(self, image_data: bytes, original_content_type: str) -> tuple[Optional[bytes], str, str]:
        """Convert image to JPG format with better error handling"""
        try:
            # Try to enable AVIF support
            try:
                from pillow_avif import AvifImagePlugin
                logger.info("[DEBUG] AVIF plugin loaded successfully")
            except ImportError:
                logger.warning("[DEBUG] AVIF plugin not available, trying without it")

            # Open the image with Pillow
            try:
                image = Image.open(io.BytesIO(image_data))
                logger.info(
                    f"[DEBUG] Successfully opened image - Format: {image.format}, Mode: {image.mode}, Size: {image.size}")
            except Exception as e:
                logger.error(f"[DEBUG] Failed to open image with Pillow: {e}")
                # Try alternative approach for AVIF
                if 'avif' in original_content_type.lower():
                    return self._convert_avif_fallback(image_data)
                return None, '', ''

            # Convert to RGB if necessary (AVIF, PNG with transparency, etc.)
            if image.mode in ('RGBA', 'LA', 'P'):
                logger.info(f"[DEBUG] Converting from {image.mode} to RGB with white background")
                # Create a white background
                background = Image.new('RGB', image.size, (255, 255, 255))
                if image.mode == 'P':
                    image = image.convert('RGBA')
                if image.mode == 'RGBA':
                    background.paste(image, mask=image.split()[-1])
                else:
                    background.paste(image)
                image = background
            elif image.mode != 'RGB':
                logger.info(f"[DEBUG] Converting from {image.mode} to RGB")
                image = image.convert('RGB')

            # Save as JPG to bytes
            output = io.BytesIO()
            image.save(output, format='JPEG', quality=85, optimize=True)
            output.seek(0)

            jpg_data = output.getvalue()

            logger.info(
                f"[DEBUG] Successfully converted to JPG - Original: {len(image_data)} bytes, JPG: {len(jpg_data)} bytes")

            return jpg_data, 'image/jpeg', '.jpg'

        except Exception as e:
            logger.error(f"[DEBUG] Error converting image to JPG: {e}")
            # Try fallback method for AVIF
            if 'avif' in original_content_type.lower():
                return self._convert_avif_fallback(image_data)
            return None, '', ''

    def _convert_avif_fallback(self, image_data: bytes) -> tuple[Optional[bytes], str, str]:
        """Fallback method for AVIF conversion using external tools"""
        try:
            import subprocess
            import tempfile

            logger.info("[DEBUG] Trying AVIF fallback conversion")

            # Create temporary files
            with tempfile.NamedTemporaryFile(suffix='.avif', delete=False) as temp_avif:
                temp_avif.write(image_data)
                temp_avif_path = temp_avif.name

            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_jpg:
                temp_jpg_path = temp_jpg.name

            try:
                # Try using imagemagick convert command
                result = subprocess.run([
                    'convert', temp_avif_path, temp_jpg_path
                ], capture_output=True, text=True, timeout=30)

                if result.returncode == 0 and os.path.exists(temp_jpg_path):
                    with open(temp_jpg_path, 'rb') as f:
                        jpg_data = f.read()

                    logger.info(f"[DEBUG] AVIF fallback conversion successful: {len(jpg_data)} bytes")
                    return jpg_data, 'image/jpeg', '.jpg'
                else:
                    logger.error(f"[DEBUG] ImageMagick conversion failed: {result.stderr}")

            except (subprocess.TimeoutExpired, FileNotFoundError) as e:
                logger.error(f"[DEBUG] ImageMagick not available or timeout: {e}")

            finally:
                # Clean up temp files
                try:
                    os.unlink(temp_avif_path)
                    os.unlink(temp_jpg_path)
                except:
                    pass

        except Exception as e:
            logger.error(f"[DEBUG] AVIF fallback conversion failed: {e}")

        return None, '', ''


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

    def _is_valid_image_url(self, url: str) -> bool:
        """Validate image URL before attempting download"""
        # Skip data URIs
        if url.startswith('data:'):
            return False

        # Skip placeholder SVGs
        if 'svg+xml' in url.lower() and ('xmlns' in url or 'svg' in url):
            return False

        # Must be HTTP/HTTPS
        if not url.startswith(('http://', 'https://')):
            return False

        # Skip obviously invalid URLs
        if len(url) < 10:
            return False

        return True
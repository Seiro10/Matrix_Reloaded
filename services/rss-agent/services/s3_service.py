import boto3
import requests
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class S3Service:
    def __init__(self):
        # Use environment variables directly
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID', ''),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY', ''),
            region_name=os.getenv('S3_REGION', 'us-east-1')
        )
        self.bucket_name = os.getenv('S3_BUCKET_NAME', 'rss-agent')

    async def upload_image_from_url(self, image_url: str, s3_key: str) -> Optional[str]:
        """Download image from URL and upload to S3"""
        try:
            logger.info(f"[DEBUG] Downloading image: {image_url}")

            response = requests.get(image_url, timeout=10)
            response.raise_for_status()

            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=response.content,
                ContentType='image/jpeg'
            )

            s3_url = f"https://{self.bucket_name}.s3.{os.getenv('S3_REGION', 'us-east-1')}.amazonaws.com/{s3_key}"
            logger.info(f"[DEBUG] Image uploaded to S3: {s3_url}")
            return s3_url

        except Exception as e:
            logger.error(f"[DEBUG] Error uploading image to S3: {e}")
            return None
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # S3 Configuration
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    s3_bucket_name: str = "your-bucket-name"
    s3_region: str = "us-east-1"

    # Redis/Queue Configuration
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"

    # Concurrency Settings
    max_concurrent_scrapers: int = 5
    max_concurrent_image_uploads: int = 10
    scraper_rate_limit: float = 1.0

    # RSS Configuration
    rss_title: str = "Gaming News RSS"
    rss_description: str = "Latest gaming news from various sources"
    rss_link: str = "http://localhost:8086"

    # Copywriter API
    copywriter_api_url: str = "http://localhost:8083/copywriter"

    # Logging
    log_level: str = "INFO"

    # Port configuration
    port: int = 8086

    class Config:
        env_file = ".env"
        # Allow extra fields to prevent validation errors
        extra = "allow"


settings = Settings()
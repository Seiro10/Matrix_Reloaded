from pydantic_settings import BaseSettings
from typing import Optional
import os
from dotenv import load_dotenv

class Settings(BaseSettings):
    # S3 Configuration
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    s3_bucket_name: str = "matrix-reloaded-rss-img-bucket"
    s3_region: str = "eu-west-3"

    # Redis/Queue Configuration
    redis_url: str = "redis://redis:6379/0"
    celery_broker_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/0"

    # Concurrency Settings
    max_concurrent_scrapers: int = 5
    max_concurrent_image_uploads: int = 10
    scraper_rate_limit: float = 1.0

    # RSS Configuration
    rss_title: str = "Gaming News RSS"
    rss_description: str = "Latest gaming news from various sources"
    rss_link: str = "http://localhost:8086"

    # Router Agent API - UPDATED
    router_agent_url: str = "http://router-agent:8080"

    # Copywriter API (keep existing for compatibility)
    copywriter_api_url: str = "http://localhost:8083/copywriter"

    # Logging
    log_level: str = "INFO"

    # Port configuration
    port: int = 8086

    class Config:
        env_file = ".env"
        extra = "allow"
        # ADD THESE:
        case_sensitive = False
        env_file_encoding = 'utf-8'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # ADD MANUAL FALLBACK:
        if not self.aws_access_key_id:
            self.aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID', '')
        if not self.aws_secret_access_key:
            self.aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY', '')

        # Debug logging
        print(
            f"[DEBUG] Loaded AWS Access Key: {self.aws_access_key_id[:10]}..." if self.aws_access_key_id else "[DEBUG] AWS Access Key: EMPTY")
        print(f"[DEBUG] Loaded AWS Secret: {'SET' if self.aws_secret_access_key else 'EMPTY'}")


settings = Settings()
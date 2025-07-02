import os

# Change defaults for local development
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

# S3 Configuration
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID', '')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY', '')
S3_BUCKET_NAME = os.getenv('S3_BUCKET_NAME', 'rss-agent')
S3_REGION = os.getenv('S3_REGION', 'us-east-1')

# Other settings
MAX_CONCURRENT_SCRAPERS = int(os.getenv('MAX_CONCURRENT_SCRAPERS', '5'))
MAX_CONCURRENT_IMAGE_UPLOADS = int(os.getenv('MAX_CONCURRENT_IMAGE_UPLOADS', '10'))
SCRAPER_RATE_LIMIT = float(os.getenv('SCRAPER_RATE_LIMIT', '1.0'))
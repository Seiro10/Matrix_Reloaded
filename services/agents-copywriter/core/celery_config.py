import os
from celery import Celery

# Environment variables with defaults
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://copywriter-redis:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://copywriter-redis:6379/0')

# Initialize Celery
celery_app = Celery(
    "copywriter_agent",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=['core.tasks']
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_routes={
        'core.tasks.process_copywriter_request': {'queue': 'copywriter'},
        'core.tasks.communicate_with_agent': {'queue': 'communication'},
        'core.tasks.wordpress_publish': {'queue': 'publishing'},
    },
    worker_concurrency=2,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_soft_time_limit=300,
    task_time_limit=600,
)
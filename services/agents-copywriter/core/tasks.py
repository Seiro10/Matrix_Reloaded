from celery import current_task
from .celery_config import celery_app
from .agent_registry import agent_registry
from models.queue_models import AgentType, TaskStatus
from metadata_model import CopywriterRequest
import logging
import requests
import json
import sys
import os
from datetime import datetime

# ADD THIS: Add the app directory to Python path
app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3)
def process_copywriter_request(self, task_id: str, request_data: dict):
    """Process a copywriter request"""
    try:
        logger.info(f"[TASK] Processing copywriter request {task_id}")

        # Convert to CopywriterRequest
        copywriter_request = CopywriterRequest(**request_data)

        # Import here to avoid circular imports (after path fix)
        from workflow.pipeline import run_full_article_pipeline

        # Run the pipeline
        result = run_full_article_pipeline(copywriter_request)

        logger.info(f"[TASK] Copywriter task {task_id} completed successfully")
        return {
            "success": True,
            "task_id": task_id,
            "result": result,
            "completed_at": datetime.now().isoformat()
        }

    except Exception as exc:
        logger.error(f"[TASK] Copywriter task {task_id} failed: {exc}")
        if self.request.retries < self.max_retries:
            logger.info(f"[TASK] Retrying task {task_id} in 60 seconds")
            raise self.retry(countdown=60, exc=exc)

        return {
            "success": False,
            "task_id": task_id,
            "error": str(exc),
            "failed_at": datetime.now().isoformat()
        }


@celery_app.task(bind=True, max_retries=3)
def communicate_with_agent(self, task_id: str, source_agent: str, target_agent: str, action: str, data: dict):
    """Handle inter-agent communication"""
    try:
        logger.info(f"[TASK] Communication {task_id}: {source_agent} -> {target_agent} ({action})")

        # Get target agent URL
        target_agent_enum = AgentType(target_agent)
        target_url = agent_registry.get_agent_url(target_agent_enum)

        if not target_url:
            raise ValueError(f"Unknown target agent: {target_agent}")

        # Prepare payload
        payload = {
            "source_agent": source_agent,
            "action": action,
            "data": data,
            "task_id": task_id
        }

        # Send request to target agent
        response = requests.post(
            f"{target_url}/agent-communication",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=120
        )

        response.raise_for_status()
        result = response.json()

        logger.info(f"[TASK] Communication {task_id} completed successfully")
        return {
            "success": True,
            "task_id": task_id,
            "result": result,
            "completed_at": datetime.now().isoformat()
        }

    except Exception as exc:
        logger.error(f"[TASK] Communication task {task_id} failed: {exc}")
        if self.request.retries < self.max_retries:
            logger.info(f"[TASK] Retrying communication {task_id} in 30 seconds")
            raise self.retry(countdown=30, exc=exc)

        return {
            "success": False,
            "task_id": task_id,
            "error": str(exc),
            "failed_at": datetime.now().isoformat()
        }


@celery_app.task(bind=True, max_retries=3)
def wordpress_publish(self, task_id: str, article_data: dict):
    """Publish article to WordPress"""
    try:
        logger.info(f"[TASK] Publishing to WordPress {task_id}")

        # Import here to avoid circular imports
        from utils.wordpress import get_jwt_token, post_article_to_wordpress, render_report_to_markdown, \
            markdown_to_html
        import os

        # Get WordPress credentials
        username = os.getenv("USERNAME_WP")
        password = os.getenv("PASSWORD_WP")

        if not username or not password:
            raise ValueError("WordPress credentials not configured")

        # Get JWT token
        token = get_jwt_token(username, password)
        if not token:
            raise ValueError("Failed to get WordPress JWT token")

        # Render article
        markdown = render_report_to_markdown(article_data)
        html = markdown_to_html(markdown)

        # Publish to WordPress
        post_id = post_article_to_wordpress(article_data, token, html=html)

        if not post_id:
            raise ValueError("Failed to publish article to WordPress")

        logger.info(f"[TASK] WordPress publish {task_id} completed, post ID: {post_id}")
        return {
            "success": True,
            "task_id": task_id,
            "post_id": post_id,
            "completed_at": datetime.now().isoformat()
        }

    except Exception as exc:
        logger.error(f"[TASK] WordPress publish {task_id} failed: {exc}")
        if self.request.retries < self.max_retries:
            logger.info(f"[TASK] Retrying WordPress publish {task_id} in 60 seconds")
            raise self.retry(countdown=60, exc=exc)

        return {
            "success": False,
            "task_id": task_id,
            "error": str(exc),
            "failed_at": datetime.now().isoformat()
        }


@celery_app.task(bind=True, name='core.tasks.process_news_copywriter')
def process_news_copywriter(self, task_id: str, request_data: dict):
    """Process news article generation task"""
    try:
        logger.info(f"[CELERY] Starting news task: {task_id}")

        from metadata_model import CopywriterRequest
        from workflow.news_pipeline import run_news_article_pipeline
        from core.queue_manager import queue_manager

        # Parse request
        request = CopywriterRequest(**request_data)

        # Update task status
        queue_manager.update_task_status(task_id, "processing")

        # Run news pipeline
        result = run_news_article_pipeline(request)

        if result:
            queue_manager.update_task_status(task_id, "completed", {"wordpress_post_id": result})
            logger.info(f"[CELERY] News task completed: {task_id}")
            return {"success": True, "wordpress_post_id": result}
        else:
            queue_manager.update_task_status(task_id, "failed", {"error": "Pipeline failed"})
            logger.error(f"[CELERY] News task failed: {task_id}")
            return {"success": False, "error": "Pipeline failed"}

    except Exception as e:
        from core.queue_manager import queue_manager
        queue_manager.update_task_status(task_id, "failed", {"error": str(e)})
        logger.error(f"[CELERY] News task error: {task_id} - {e}")
        raise
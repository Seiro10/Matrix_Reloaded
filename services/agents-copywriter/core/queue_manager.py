from celery import Celery
from .celery_config import celery_app
from models.queue_models import AgentTask, TaskType, AgentType, TaskStatus
from typing import Optional, Dict, Any
import logging
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)


class QueueManager:
    def __init__(self):
        self.celery = celery_app

    def queue_copywriter_task(self, request_data: dict, priority: int = 5) -> str:
        """Queue a copywriter task"""
        from core.tasks import process_copywriter_request

        task_id = str(uuid.uuid4())
        logger.info(f"[QUEUE] Queuing copywriter task {task_id}")

        result = process_copywriter_request.apply_async(
            args=[task_id, request_data],
            priority=priority,
            queue='copywriter',
            task_id=task_id
        )
        return task_id

    def queue_agent_communication(
            self,
            source_agent: AgentType,
            target_agent: AgentType,
            action: str,
            data: dict,
            priority: int = 5
    ) -> str:
        """Queue inter-agent communication"""
        from core.tasks import communicate_with_agent

        task_id = str(uuid.uuid4())
        logger.info(f"[QUEUE] Queuing communication {source_agent.value} -> {target_agent.value}")

        result = communicate_with_agent.apply_async(
            args=[task_id, source_agent.value, target_agent.value, action, data],
            priority=priority,
            queue='communication',
            task_id=task_id
        )
        return task_id

    def queue_wordpress_publish(self, article_data: dict, priority: int = 5) -> str:
        """Queue WordPress publishing task"""
        from core.tasks import wordpress_publish

        task_id = str(uuid.uuid4())
        logger.info(f"[QUEUE] Queuing WordPress publish task {task_id}")

        result = wordpress_publish.apply_async(
            args=[task_id, article_data],
            priority=priority,
            queue='publishing',
            task_id=task_id
        )
        return task_id

    def queue_news_task(self, request_data: dict, priority: int = 5) -> str:
        """Queue a news article generation task"""
        task_id = f"news_{uuid.uuid4()}"

        try:
            # Use the same pattern as existing tasks
            result = self.celery_app.send_task(
                'core.tasks.process_news_copywriter',  # Task name
                args=[task_id, request_data],
                task_id=task_id,
                priority=priority,
                routing_key='copywriter'
            )

            # Store task info using existing pattern
            self.active_tasks[task_id] = {
                "task_id": task_id,
                "type": AgentType.COPYWRITER_NEWS.value,  # We'll need to add this enum
                "status": "queued",
                "created_at": datetime.now().isoformat(),
                "celery_task_id": result.id,
                "request_data": request_data
            }

            logger.info(f"[QUEUE] Queued news task: {task_id}")
            return task_id

        except Exception as e:
            logger.error(f"[QUEUE] Error queuing news task: {e}")
            raise

    def get_task_status(self, task_id: str) -> dict:
        """Get task status"""
        result = self.celery.AsyncResult(task_id)
        return {
            "task_id": task_id,
            "status": result.status,
            "result": result.result if result.ready() else None,
            "info": result.info
        }

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a task"""
        try:
            self.celery.control.revoke(task_id, terminate=True)
            return True
        except Exception as e:
            logger.error(f"[QUEUE] Error canceling task {task_id}: {e}")
            return False


# Global queue manager instance
queue_manager = QueueManager()
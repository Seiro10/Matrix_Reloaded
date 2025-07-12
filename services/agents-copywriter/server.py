from fastapi import FastAPI, HTTPException
from metadata_model import CopywriterRequest
from core.queue_manager import queue_manager
from core.agent_registry import agent_registry
from models.queue_models import AgentType
import logging

logger = logging.getLogger(__name__)

app = FastAPI(title="Copywriter Agent API")


@app.post("/copywriter")
async def write_article(request: CopywriterRequest):
    """Queue article generation request"""
    try:
        # Queue the task
        task_id = queue_manager.queue_copywriter_task(
            request_data=request.model_dump(),
            priority=5
        )

        logger.info(f"[API] Queued copywriter request {task_id}")

        return {
            "success": True,
            "message": "Request queued successfully",
            "task_id": task_id,
            "status": "queued"
        }

    except Exception as e:
        logger.error(f"[API] Error queuing request: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/copywriter/status/{task_id}")
async def get_task_status(task_id: str):
    """Get status of a copywriter task"""
    try:
        status = queue_manager.get_task_status(task_id)
        return status
    except Exception as e:
        logger.error(f"[API] Error getting task status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/agent-communication")
async def agent_communication(payload: dict):
    """Handle communication from other agents"""
    try:
        source_agent = payload.get("source_agent")
        action = payload.get("action")
        data = payload.get("data", {})

        logger.info(f"[API] Received communication from {source_agent}: {action}")

        # Process based on action
        if action == "request_article":
            # Queue copywriter task
            task_id = queue_manager.queue_copywriter_task(data)
            return {"success": True, "task_id": task_id}

        elif action == "publish_article":
            # Queue WordPress publish
            task_id = queue_manager.queue_wordpress_publish(data)
            return {"success": True, "task_id": task_id}

        else:
            return {"success": False, "error": f"Unknown action: {action}"}

    except Exception as e:
        logger.error(f"[API] Error in agent communication: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    # Check Celery workers
    try:
        from core.celery_config import celery_app
        inspect = celery_app.control.inspect()
        stats = inspect.stats()
        active_workers = len(stats) if stats else 0
    except:
        active_workers = 0

    return {
        "status": "healthy",
        "service": "copywriter_agent",
        "celery_workers": active_workers,
        "registered_agents": len(agent_registry.get_all_agents())
    }


@app.post("/copywriter-news")
async def write_news_article(request: CopywriterRequest):
    """Generate news article without interviews"""
    try:
        # Import here to avoid circular imports
        from core.queue_manager import queue_manager

        # Queue the news task
        task_id = queue_manager.queue_news_task(
            request_data=request.model_dump(),
            priority=5
        )

        logger.info(f"[API] Queued news request {task_id}")

        return {
            "success": True,
            "message": "News request queued successfully",
            "task_id": task_id,
            "status": "queued"
        }

    except Exception as e:
        logger.error(f"[API] Error queuing news request: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/agents")
async def list_agents():
    """List all registered agents"""
    return {
        "agents": {
            agent_type.value: config
            for agent_type, config in agent_registry.get_all_agents().items()
        }
    }
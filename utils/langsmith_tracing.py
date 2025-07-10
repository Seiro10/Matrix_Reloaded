# utils/langsmith_tracing.py
"""
LangSmith tracing utilities for cross-agent communication
"""

import os
import uuid
from typing import Dict, Any, Optional
from functools import wraps
import httpx
from langsmith import Client, traceable
from langsmith.run_helpers import get_current_run_tree
import logging

logger = logging.getLogger(__name__)


class LangSmithTracker:
    """Centralized LangSmith tracking for multi-agent systems"""

    def __init__(self, project_name: str = None):
        self.client = Client() if os.getenv("LANGCHAIN_TRACING_V2") == "true" else None
        self.project_name = project_name or os.getenv("LANGCHAIN_PROJECT", "content-agents")
        self.enabled = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"

        if self.enabled:
            logger.info(f"LangSmith tracing enabled for project: {self.project_name}")
        else:
            logger.info("LangSmith tracing disabled")

    def get_trace_headers(self) -> Dict[str, str]:
        """Get trace headers for HTTP requests to maintain trace context"""
        headers = {}

        if not self.enabled:
            return headers

        try:
            current_run = get_current_run_tree()
            if current_run:
                headers.update({
                    "X-Trace-ID": str(current_run.trace_id) if current_run.trace_id else str(uuid.uuid4()),
                    "X-Parent-Run-ID": str(current_run.id) if current_run.id else "",
                    "X-LangSmith-Project": self.project_name
                })
        except Exception as e:
            logger.warning(f"Failed to get trace context: {e}")
            # Generate new trace ID if we can't get current context
            headers["X-Trace-ID"] = str(uuid.uuid4())
            headers["X-LangSmith-Project"] = self.project_name

        return headers

    def extract_trace_context(self, headers: Dict[str, str]) -> Dict[str, Any]:
        """Extract trace context from incoming HTTP headers"""
        return {
            "trace_id": headers.get("X-Trace-ID"),
            "parent_run_id": headers.get("X-Parent-Run-ID"),
            "project": headers.get("X-LangSmith-Project", self.project_name)
        }


def trace_agent_communication(agent_name: str, operation: str):
    """Decorator to trace agent-to-agent communication"""

    def decorator(func):
        @wraps(func)
        @traceable(name=f"{agent_name}_{operation}")
        async def async_wrapper(*args, **kwargs):
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                logger.error(f"Error in {agent_name} {operation}: {e}")
                raise

        @wraps(func)
        @traceable(name=f"{agent_name}_{operation}")
        def sync_wrapper(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                logger.error(f"Error in {agent_name} {operation}: {e}")
                raise

        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


class TracedHTTPClient:
    """HTTP client that maintains trace context across agent calls"""

    def __init__(self, base_url: str = None, timeout: int = 30):
        self.base_url = base_url
        self.timeout = timeout
        self.tracker = LangSmithTracker()

    async def post(self, url: str, json_data: Dict[str, Any], headers: Dict[str, str] = None) -> Dict[str, Any]:
        """Make traced POST request"""

        # Combine trace headers with any provided headers
        trace_headers = self.tracker.get_trace_headers()
        if headers:
            trace_headers.update(headers)

        # Add content type
        trace_headers["Content-Type"] = "application/json"

        full_url = f"{self.base_url}{url}" if self.base_url else url

        with traceable(name=f"http_post_to_{url.split('/')[-1]}")() as run:
            run.inputs = {"url": full_url, "payload": json_data}

            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        full_url,
                        json=json_data,
                        headers=trace_headers
                    )
                    response.raise_for_status()
                    result = response.json()

                    run.outputs = {"status_code": response.status_code, "response": result}
                    return result

            except Exception as e:
                run.error = str(e)
                logger.error(f"HTTP request failed: {e}")
                raise


def setup_langsmith_for_service(service_name: str):
    """Setup LangSmith configuration for a specific service"""

    # Set service-specific project name if not already set
    current_project = os.getenv("LANGCHAIN_PROJECT")
    if not current_project or not current_project.endswith(f"-{service_name}"):
        base_project = os.getenv("LANGCHAIN_PROJECT", "content-agents").split("-")[0]
        os.environ["LANGCHAIN_PROJECT"] = f"{base_project}-{service_name}"

    # Ensure tracing is enabled
    os.environ["LANGCHAIN_TRACING_V2"] = "true"

    logger.info(f"LangSmith configured for {service_name} - Project: {os.getenv('LANGCHAIN_PROJECT')}")


# FastAPI middleware for trace context
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class LangSmithTracingMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware to handle trace context in HTTP requests"""

    def __init__(self, app, service_name: str):
        super().__init__(app)
        self.service_name = service_name
        self.tracker = LangSmithTracker()

    async def dispatch(self, request: Request, call_next):
        # Extract trace context from headers
        trace_context = self.tracker.extract_trace_context(dict(request.headers))

        # Add trace context to request state
        request.state.trace_context = trace_context

        # Process request with tracing
        with traceable(
                name=f"{self.service_name}_request_{request.method}_{request.url.path}",
                project_name=trace_context.get("project", self.tracker.project_name)
        )() as run:
            run.inputs = {
                "method": request.method,
                "url": str(request.url),
                "headers": dict(request.headers),
                "trace_context": trace_context
            }

            try:
                response = await call_next(request)
                run.outputs = {"status_code": response.status_code}
                return response

            except Exception as e:
                run.error = str(e)
                raise
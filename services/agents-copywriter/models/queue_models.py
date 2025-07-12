from pydantic import BaseModel
from typing import Dict, Any, Optional, List
from enum import Enum
from datetime import datetime

class TaskStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRY = "retry"

class AgentType(Enum):
    COPYWRITER = "copywriter"
    METADATA_GENERATOR = "metadata_generator"
    COPYWRITER_NEWS = "copywriter_news"
    REWRITER = "rewriter"

class TaskType(Enum):
    COPYWRITER_REQUEST = "copywriter_request"
    AGENT_COMMUNICATION = "agent_communication"
    WORDPRESS_PUBLISH = "wordpress_publish"

class AgentTask(BaseModel):
    task_id: str
    task_type: TaskType
    source_agent: Optional[AgentType] = None
    target_agent: Optional[AgentType] = None
    payload: Dict[str, Any]
    priority: int = 5
    max_retries: int = 3
    retry_count: int = 0
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: TaskStatus = TaskStatus.PENDING
    error_message: Optional[str] = None
    result: Optional[Dict[str, Any]] = None

class AgentCommunicationPayload(BaseModel):
    source_agent: AgentType
    target_agent: AgentType
    action: str
    data: Dict[str, Any]
    callback_queue: Optional[str] = None
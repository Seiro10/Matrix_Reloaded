"""
Data models for Rewriter Agent
"""

from typing import Dict, List, Optional, Literal, Any
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CompetitorData(BaseModel):
    """Structure for competitor analysis data"""
    position: int
    title: str
    url: str
    snippet: str
    content: str
    structure: str
    headlines: List[str]
    metadescription: str


class RewriterInput(BaseModel):
    """Input data structure from CSV"""
    keyword: str
    competition: str
    url_to_rewrite: str
    site: str
    confidence: float
    monthly_searches: int
    people_also_ask: List[str]
    forum: List[str]
    competitors: List[CompetitorData]


class ArticleContent(BaseModel):
    """WordPress article content structure"""
    id: int
    title: str
    content: str
    slug: str
    meta_description: str
    featured_image: Optional[str] = None
    tags: List[str] = []
    categories: List[str] = []


class RewritingStrategy(BaseModel):
    """LLM-generated rewriting strategy"""
    sections_to_update: List[str] = Field(description="List of sections that need updating")
    content_to_add: str = Field(description="New content to integrate")
    outdated_elements: List[str] = Field(description="Outdated information to replace")
    seo_improvements: List[str] = Field(description="SEO enhancement suggestions")
    tone_adjustments: str = Field(description="Any tone or style adjustments needed")


class RewriterState(BaseModel):
    """State management for Rewriter Agent"""
    input_data: Optional[RewriterInput] = None
    original_article: Optional[ArticleContent] = None
    competitor_insights: Optional[Dict[str, Any]] = None
    rewriting_strategy: Optional[RewritingStrategy] = None
    updated_content: Optional[str] = None
    wordpress_response: Optional[Dict[str, Any]] = None
    errors: List[str] = []
    metadata: Dict[str, Any] = {}


# Response models for API
class RewriterResponse(BaseModel):
    success: bool
    session_id: Optional[str] = None
    article_id: Optional[int] = None
    wordpress_response: Optional[Dict[str, Any]] = None
    result_file: Optional[str] = None
    errors: Optional[list] = None
    error: Optional[str] = None
    message: str


class RewriterStatus(BaseModel):
    session_id: str
    status: str
    progress: str
    errors: Optional[list] = None
    result: Optional[Dict[str, Any]] = None


class RewriterRequestBody(BaseModel):
    keyword: str
    url_to_rewrite: str
    site: str
    confidence: float
    monthly_searches: int
    people_also_ask: list = []
    forum: list = []
    competitors: list = []
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional


class MetadataOutput(BaseModel):
    """Output metadata structure"""
    url: str = Field(description="Best possible URL based on competitor and SERP info")
    main_kw: str = Field(description="Main keyword")
    secondary_kws: List[str] = Field(description="Secondary keywords (max 3)")
    meta_description: str = Field(description="Meta description (160 chars max)")
    post_type: str = Field(description="Type of post (Affiliate, News, or Guide)")
    headlines: List[str] = Field(description="List of headlines based on competitor content")
    language: str = Field(description="Content language (e.g., FR, EN)")


class MetadataResponse(BaseModel):
    """API response model"""
    success: bool
    session_id: str
    message: str
    metadata: Optional[MetadataOutput] = None
    error: Optional[str] = None
    # Add copywriter response fields
    copywriter_response: Optional[Dict[str, Any]] = None
    article_id: Optional[str] = None
    content: Optional[str] = None
    status: Optional[str] = None


class CompetitorData(BaseModel):
    """Competitor data structure"""
    position: str = ""
    title: str = ""
    url: str = ""
    snippet: str = ""
    content: str = ""
    structure: str = ""
    headlines: List[str] = []
    metadescription: str = ""


class ParsedInputData(BaseModel):
    """Parsed CSV input data structure"""
    keyword: str = ""
    competition: str = ""
    site: str = ""
    language: str = "FR"
    post_type: str = ""
    confidence: float = 0.0
    monthly_searches: int = 0
    people_also_ask: List[str] = []
    forum: List[str] = []
    banner_image: str = ""
    original_post_url: str = ""
    competitors: List[CompetitorData] = []
    source_content: str = ""
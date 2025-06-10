from typing import Dict, List, Optional, Literal, Any
from pydantic import BaseModel, Field
from typing_extensions import TypedDict

# Input Models (from Content Finder Agent)
class SimilarKeyword(BaseModel):
    keyword: str
    monthly_searches: int
    competition: str

class TopResult(BaseModel):
    url: str
    title: str
    meta_description: str
    content: str
    content_structure: List[str]
    publication_date: str

class SERPAnalysis(BaseModel):
    top_results: List[TopResult]
    people_also_ask: List[str]

class ContentFinderOutput(BaseModel):
    keyword: str
    similar_keywords: List[SimilarKeyword]
    serp_analysis: SERPAnalysis

# Internal State Models
class RouterState(TypedDict):
    input_data: ContentFinderOutput
    selected_site: Optional[Dict[str, Any]]
    existing_content: Optional[Dict[str, Any]]
    routing_decision: Optional[Literal["copywriter", "rewriter"]]
    confidence_score: Optional[float]
    internal_linking_suggestions: Optional[List[str]]
    reasoning: Optional[str]
    output_payload: Optional[Dict[str, Any]]

# Output Models
class SiteInfo(BaseModel):
    site_id: int
    name: str
    domain: str
    niche: str
    theme: str
    language: str
    sitemap_url: str
    wordpress_api_url: str

class RoutingMetadata(BaseModel):
    confidence_score: float
    content_source: Optional[str] = None
    timestamp: str

class OutputPayload(BaseModel):
    agent_target: Literal["copywriter", "rewriter"]
    keyword: str
    site_config: SiteInfo
    serp_analysis: SERPAnalysis
    similar_keywords: List[SimilarKeyword]
    internal_linking_suggestions: List[str]
    routing_metadata: RoutingMetadata
    existing_content: Optional[Dict[str, Any]] = None

class RouterResponse(BaseModel):
    success: bool
    routing_decision: Optional[Literal["copywriter", "rewriter"]] = None
    selected_site: Optional[SiteInfo] = None
    confidence_score: Optional[float] = None
    reasoning: Optional[str] = None
    payload: Optional[OutputPayload] = None
    internal_linking_suggestions: Optional[List[str]] = None
    error: Optional[str] = None

# Database Models
class ArticleRecord(BaseModel):
    id: int
    site_id: int
    url: str
    title: str
    slug: str
    content: str
    keywords: str
    meta_description: str
    status: str
    similarity_reason: Optional[str] = None
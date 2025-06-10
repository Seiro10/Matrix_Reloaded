from typing import Dict, List, Optional, Literal, Any
from pydantic import BaseModel, Field
from typing_extensions import TypedDict
from datetime import datetime


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


class OrganicResult(BaseModel):
    position: int
    title: str
    url: str
    snippet: str
    content: Optional[str] = None
    structure: Optional[str] = None
    headlines: Optional[List[str]] = None
    metadescription: Optional[str] = None

class KeywordData(BaseModel):
    keyword: str
    competition: str
    monthly_searches: int
    people_also_ask: List[str]
    people_also_search_for: List[str]
    organic_results: List[OrganicResult]
    forum: List[str]
    total_results_found: int


class ContentFinderOutput(BaseModel):
    keywords_data: Dict[str, KeywordData]

    def get_primary_keyword(self) -> str:
        """Return the first keyword as primary"""
        return list(self.keywords_data.keys())[0] if self.keywords_data else ""

    def get_similar_keywords(self) -> List[SimilarKeyword]:
        """Build similar keywords from people_also_search_for of primary keyword"""
        if not self.keywords_data:
            return []

        primary_data = list(self.keywords_data.values())[0]
        similar = []

        for term in primary_data.people_also_search_for[:5]:  # Limit to 5
            similar.append(SimilarKeyword(
                keyword=term,
                monthly_searches=0,  # Default
                competition="UNKNOWN"
            ))

        return similar

    def get_serp_analysis(self) -> SERPAnalysis:
        """Build SERP analysis from organic results of primary keyword"""
        if not self.keywords_data:
            return SERPAnalysis(top_results=[], people_also_ask=[])

        primary_data = list(self.keywords_data.values())[0]
        top_results = []

        for result in primary_data.organic_results[:3]:  # Top 3
            # Parse structure HTML to array
            content_structure = self._parse_structure(result.structure or "")

            top_results.append(TopResult(
                url=result.url,
                title=result.title,
                meta_description=result.metadescription or result.snippet,
                content=result.content or "",
                content_structure=content_structure,
                publication_date=datetime.now().isoformat()
            ))

        return SERPAnalysis(
            top_results=top_results,
            people_also_ask=primary_data.people_also_ask[:4]
        )

    def _parse_structure(self, html_structure: str) -> List[str]:
        """Parse HTML structure into array"""
        if not html_structure:
            return []

        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_structure, 'html.parser')
            structure = []

            for tag in soup.find_all(['h1', 'h2', 'h3', 'h4']):
                clean_text = tag.get_text(strip=True)
                if clean_text:
                    structure.append(clean_text)

            return structure[:10]
        except:
            return []



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

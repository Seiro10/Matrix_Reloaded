from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class MetadataInput(BaseModel):
    """Metadata structure from metadata-generator agent"""
    url: str = Field(description="Best possible URL based on competitor and SERP info")
    title: str = Field(description="Article title optimized for SEO")  # ADD THIS
    main_kw: str = Field(description="Main keyword")
    secondary_kws: List[str] = Field(description="Secondary keywords (max 3)")
    meta_description: str = Field(description="Meta description (160 chars max)")
    post_type: str = Field(description="Type of post (Affiliate, News, or Guide)")
    headlines: List[str] = Field(description="List of headlines based on competitor content")
    language: str = Field(description="Content language (e.g., FR, EN)")


class CopywriterRequest(BaseModel):
    metadata: MetadataInput
    keyword_data: dict = Field(default_factory=dict)
    session_metadata: dict = Field(default_factory=dict)
    audience: str = Field(default="gaming enthusiasts")
    number_of_journalists: int = Field(default=3)
    max_turns: int = Field(default=3)

    @property
    def banner_image(self) -> str:
        """Extract banner image from keyword_data"""
        return self.keyword_data.get("banner_image", "")

    @property
    def source_content(self) -> str:
        """Extract source content from keyword_data"""
        return self.keyword_data.get("source_content", "")
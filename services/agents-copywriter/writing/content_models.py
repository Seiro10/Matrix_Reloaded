from pydantic import BaseModel, Field
from typing import List, Optional, Literal

class ContentBlock(BaseModel):
    type: Literal["paragraph", "bullet_list", "numbered_list", "table", "pros_cons"]
    content: str = Field(description="Main text content or description")
    items: Optional[List[str]] = Field(default=None, description="List items for bullet_list or numbered_list")
    table_data: Optional[List[List[str]]] = Field(default=None, description="Table data as rows and columns")
    pros: Optional[List[str]] = Field(default=None, description="Advantages for pros_cons type")
    cons: Optional[List[str]] = Field(default=None, description="Disadvantages for pros_cons type")

    class Config:
        extra = "forbid"  # This is required for OpenAI structured output

class StructuredSection(BaseModel):
    heading: str = Field(description="Section heading")
    blocks: List[ContentBlock] = Field(description="Content blocks that make up this section")

    class Config:
        extra = "forbid"

class StructuredComparison(BaseModel):
    title: str
    product: str
    description: str
    content_blocks: List[ContentBlock] = Field(description="Structured content for this comparison")

    class Config:
        extra = "forbid"

class FAQItem(BaseModel):
    question: str
    answer: str

    class Config:
        extra = "forbid"

class StructuredAffiliate(BaseModel):
    title: str
    introduction: StructuredSection
    comparisons: List[StructuredComparison]
    notable_mentions: List[StructuredSection]
    conclusion: StructuredSection
    faq: List[FAQItem]

    class Config:
        extra = "forbid"

class StructuredGuideNews(BaseModel):
    title: str
    introduction: StructuredSection
    main_sections: List[StructuredSection]
    conclusion: StructuredSection
    faq: List[FAQItem]

    class Config:
        extra = "forbid"
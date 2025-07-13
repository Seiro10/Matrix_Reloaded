from pydantic import BaseModel, HttpUrl
from typing import List, Optional
from datetime import datetime

class NewsItem(BaseModel):
    title: str
    content: str
    images: List[str]
    website: str
    destination_website: str
    theme: str
    url: str
    published_date: datetime
    s3_image_urls: Optional[List[str]] = []
    banner_image: Optional[str] = None
    post_type: str = "News"

class RSSFeedData(BaseModel):
    items: List[NewsItem]
    last_updated: datetime

class CopywriterPayload(BaseModel):
    title: str
    content: str
    images: List[str]
    website: str
    destination_website: str
    theme: str
    url: str
    s3_image_urls: List[str]
    banner_image: Optional[str] = None
    original_post_url: str
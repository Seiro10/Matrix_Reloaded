from typing import Dict, Any, Optional, List, Union
from typing_extensions import TypedDict


class ArticleRewriterState(TypedDict):
    """State for the article rewriter workflow - FIXED to handle BeautifulSoup objects properly"""

    # Input data
    article_url: str
    subject: str
    additional_content: str  # Content to integrate (replaces YouTube transcript)

    # Processing data
    original_html: Optional[str]
    temp_file_path: Optional[str]
    # CRITICAL: These must accept Any to handle BeautifulSoup Tag objects
    html_blocks: Optional[List[Dict[str, Any]]]  # Contains BeautifulSoup Tag objects
    updated_blocks: Optional[List[Dict[str, Any]]]  # Contains BeautifulSoup Tag objects
    reconstructed_html: Optional[str]
    diagnostic: Optional[str]
    generated_sections: Optional[str]
    final_html: Optional[str]

    # WordPress data
    slug: Optional[str]
    post_id: Optional[int]
    jwt_token: Optional[str]

    # Status and error handling
    status: str  # initialized, processing, completed, error
    error: Optional[str]

    # Memory for multi-step processing
    memory: Optional[Dict[str, Any]]
from typing import Optional


class ArticleUpdateRequest:
    def __init__(self, article_url: str, subject: str, additional_content: str):
        self.article_url = article_url
        self.subject = subject
        self.additional_content = additional_content


class ArticleUpdateResponse:
    def __init__(self, message: str, updated_html: str, post_id: Optional[int] = None, status: str = "success"):
        self.message = message
        self.updated_html = updated_html
        self.post_id = post_id
        self.status = status
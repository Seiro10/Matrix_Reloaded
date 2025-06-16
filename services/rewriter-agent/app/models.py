from pydantic import BaseModel, HttpUrl
from typing import Optional


class ArticleUpdateRequest(BaseModel):
    article_url: str
    subject: str
    additional_content: str  # This replaces the YouTube transcript content

    class Config:
        schema_extra = {
            "example": {
                "article_url": "https://stuffgaming.fr/some-article-slug/",
                "subject": "Guide complet du jeu XYZ",
                "additional_content": "Voici les nouvelles informations à intégrer dans l'article..."
            }
        }


class ArticleUpdateResponse(BaseModel):
    message: str
    updated_html: str
    post_id: Optional[int] = None
    status: str

    class Config:
        schema_extra = {
            "example": {
                "message": "✅ Article mis à jour avec succès (ID 123)",
                "updated_html": "<p>Article content...</p>",
                "post_id": 123,
                "status": "success"
            }
        }


class CSVUploadResponse(BaseModel):
    session_id: str
    message: str
    updated_html: str
    post_id: Optional[int] = None
    status: str
    processed_url: str
    processed_subject: str

    class Config:
        schema_extra = {
            "example": {
                "session_id": "csv_final_fantasy_14_abc123",
                "message": "✅ Article mis à jour avec succès (ID 123)",
                "updated_html": "<p>Article content...</p>",
                "post_id": 123,
                "status": "success",
                "processed_url": "https://stuffgaming.fr/final-fantasy-14-avis/",
                "processed_subject": "final fantasy 14"
            }
        }
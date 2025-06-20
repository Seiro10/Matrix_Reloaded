import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Anthropic settings
    anthropic_api_key: str

    # OpenAI / LangSmith (ajouté)
    openai_api_key: str
    langsmith_tracing: bool = False
    langsmith_endpoint: str = "https://api.smith.langchain.com"
    langchain_api_key: str
    langsmith_project: str = "default"

    # WordPress settings
    username_wp: str
    password_wp: str
    wordpress_base_url: str = "https://stuffgaming.fr"

    # File paths
    temp_dir: str = "./temp"
    logs_dir: str = "./logs"
    generated_dir: str = "./generated"

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "forbid"  # 🚫 Rejette les clés inconnues


# Global settings instance
settings = Settings()
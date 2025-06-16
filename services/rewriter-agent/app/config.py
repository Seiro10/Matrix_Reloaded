import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Anthropic settings (CHANGED from openai_api_key)
    anthropic_api_key: str

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


# Global settings instance
settings = Settings()
"""
Rewriter Agent - Configuration Management
src/config.py
"""

import os
from typing import List, Optional
from pydantic import BaseSettings, Field, validator
from pathlib import Path


class Settings(BaseSettings):
    """Application settings with environment variable support"""

    # Application settings
    app_name: str = Field(default="Rewriter Agent", description="Application name")
    version: str = Field(default="1.0.0", description="Application version")
    environment: str = Field(default="development", description="Environment (development/production)")
    debug: bool = Field(default=False, description="Debug mode")

    # Server settings
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8082, description="Server port")
    workers: int = Field(default=1, description="Number of worker processes")

    # API Keys
    anthropic_api_key: str = Field(..., description="Anthropic API key for Claude")
    openai_api_key: Optional[str] = Field(None, description="Optional OpenAI API key")

    # WordPress Configuration
    wordpress_api_url: str = Field(..., description="WordPress REST API base URL")
    wordpress_username: str = Field(..., description="WordPress username")
    wordpress_password: str = Field(..., description="WordPress password")
    wordpress_timeout: int = Field(default=30, description="WordPress API timeout in seconds")
    wordpress_retry_attempts: int = Field(default=3, description="WordPress API retry attempts")

    # File paths
    output_dir: str = Field(default="./output", description="Output directory for results")
    logs_dir: str = Field(default="./logs", description="Logs directory")
    temp_dir: str = Field(default="./temp", description="Temporary files directory")

    # Processing limits
    max_content_length: int = Field(default=100000, description="Maximum content length to process")
    min_content_length: int = Field(default=100, description="Minimum content length to process")
    max_processing_time: int = Field(default=300, description="Maximum processing time in seconds")
    max_concurrent_sessions: int = Field(default=10, description="Maximum concurrent processing sessions")
    max_bulk_files: int = Field(default=5, description="Maximum files in bulk processing")

    # LLM Configuration
    llm_model: str = Field(default="claude-3-5-sonnet-20241022", description="Default LLM model")
    llm_temperature: float = Field(default=0.3, description="LLM temperature setting")
    llm_max_tokens: int = Field(default=4000, description="Maximum LLM tokens")
    llm_timeout: int = Field(default=60, description="LLM API timeout in seconds")

    # Security and CORS
    allowed_origins: List[str] = Field(
        default=["*"],
        description="Allowed CORS origins"
    )
    api_key_required: bool = Field(default=False, description="Whether API key is required")
    rate_limit_requests: int = Field(default=100, description="Rate limit requests per minute")

    # Feature flags
    enable_caching: bool = Field(default=True, description="Enable response caching")
    enable_metrics: bool = Field(default=True, description="Enable metrics collection")
    enable_detailed_logs: bool = Field(default=True, description="Enable detailed logging")
    preserve_media: bool = Field(default=True, description="Preserve media elements by default")
    preserve_links: bool = Field(default=True, description="Preserve internal links by default")
    seo_optimization: bool = Field(default=True, description="Apply SEO optimizations by default")

    # Cleanup settings
    auto_cleanup_temp_files: bool = Field(default=True, description="Automatically cleanup temp files")
    temp_file_retention_hours: int = Field(default=24, description="Hours to retain temp files")
    log_retention_days: int = Field(default=30, description="Days to retain log files")

    @validator('environment')
    def validate_environment(cls, v):
        if v not in ['development', 'staging', 'production']:
            raise ValueError('Environment must be development, staging, or production')
        return v

    @validator('port')
    def validate_port(cls, v):
        if not 1 <= v <= 65535:
            raise ValueError('Port must be between 1 and 65535')
        return v

    @validator('llm_temperature')
    def validate_temperature(cls, v):
        if not 0.0 <= v <= 2.0:
            raise ValueError('LLM temperature must be between 0.0 and 2.0')
        return v

    @validator('output_dir', 'logs_dir', 'temp_dir')
    def create_directories(cls, v):
        """Create directories if they don't exist"""
        Path(v).mkdir(parents=True, exist_ok=True)
        return v

    @validator('wordpress_api_url')
    def validate_wordpress_url(cls, v):
        """Ensure WordPress URL ends with /wp-json"""
        if not v.endswith('/wp-json') and not v.endswith('/wp-json/'):
            if v.endswith('/'):
                v = v + 'wp-json'
            else:
                v = v + '/wp-json'
        return v

    @property
    def is_development(self) -> bool:
        """Check if running in development mode"""
        return self.environment.lower() == 'development'

    @property
    def is_production(self) -> bool:
        """Check if running in production mode"""
        return self.environment.lower() == 'production'

    @property
    def database_url(self) -> str:
        """Get database URL for session storage (if using external DB)"""
        return os.getenv('DATABASE_URL', 'sqlite:///./rewriter_sessions.db')

    @property
    def redis_url(self) -> Optional[str]:
        """Get Redis URL for caching (if using Redis)"""
        return os.getenv('REDIS_URL')

    @property
    def sentry_dsn(self) -> Optional[str]:
        """Get Sentry DSN for error tracking"""
        return os.getenv('SENTRY_DSN')

    def get_wordpress_headers(self) -> dict:
        """Get standard WordPress API headers"""
        return {
            'Content-Type': 'application/json',
            'User-Agent': f'{self.app_name}/{self.version}'
        }

    def get_llm_config(self) -> dict:
        """Get LLM configuration parameters"""
        return {
            'model': self.llm_model,
            'temperature': self.llm_temperature,
            'max_tokens': self.llm_max_tokens,
            'timeout': self.llm_timeout
        }

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

        # Environment variable prefix
        env_prefix = "REWRITER_"

        # Field aliases for backward compatibility
        fields = {
            'anthropic_api_key': {'env': ['ANTHROPIC_API_KEY', 'REWRITER_ANTHROPIC_API_KEY']},
            'openai_api_key': {'env': ['OPENAI_API_KEY', 'REWRITER_OPENAI_API_KEY']},
            'wordpress_api_url': {'env': ['WORDPRESS_API_URL', 'REWRITER_WORDPRESS_API_URL']},
            'wordpress_username': {'env': ['WORDPRESS_USERNAME', 'REWRITER_WORDPRESS_USERNAME']},
            'wordpress_password': {'env': ['WORDPRESS_PASSWORD', 'REWRITER_WORDPRESS_PASSWORD']},
            'environment': {'env': ['ENVIRONMENT', 'REWRITER_ENVIRONMENT']},
            'port': {'env': ['PORT', 'REWRITER_PORT']},
        }


class LoggingConfig:
    """Logging configuration"""

    @staticmethod
    def get_config(settings: Settings) -> dict:
        """Get logging configuration based on settings"""

        log_level = "DEBUG" if settings.debug else "INFO"

        config = {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "standard": {
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                    "datefmt": "%Y-%m-%d %H:%M:%S"
                },
                "detailed": {
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(module)s - %(funcName)s - %(lineno)d - %(message)s",
                    "datefmt": "%Y-%m-%d %H:%M:%S"
                },
                "json": {
                    "class": "pythonjsonlogger.jsonlogger.JsonFormatter",
                    "format": "%(asctime)s %(name)s %(levelname)s %(module)s %(funcName)s %(lineno)d %(message)s"
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "level": log_level,
                    "formatter": "standard" if not settings.enable_detailed_logs else "detailed",
                    "stream": "ext://sys.stdout"
                },
                "file": {
                    "class": "logging.handlers.RotatingFileHandler",
                    "level": log_level,
                    "formatter": "detailed",
                    "filename": os.path.join(settings.logs_dir, "rewriter_agent.log"),
                    "maxBytes": 10485760,  # 10MB
                    "backupCount": 5,
                    "encoding": "utf-8"
                }
            },
            "loggers": {
                "": {  # Root logger
                    "level": log_level,
                    "handlers": ["console", "file"]
                },
                "uvicorn": {
                    "level": "INFO",
                    "handlers": ["console", "file"],
                    "propagate": False
                },
                "uvicorn.access": {
                    "level": "INFO",
                    "handlers": ["file"],
                    "propagate": False
                },
                "anthropic": {
                    "level": "WARNING",
                    "handlers": ["file"],
                    "propagate": False
                }
            }
        }

        # Add JSON logging for production
        if settings.is_production:
            config["handlers"]["json_file"] = {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "INFO",
                "formatter": "json",
                "filename": os.path.join(settings.logs_dir, "rewriter_agent.json"),
                "maxBytes": 10485760,
                "backupCount": 10,
                "encoding": "utf-8"
            }
            config["loggers"][""]["handlers"].append("json_file")

        return config


# Global settings instance
try:
    settings = Settings()
except Exception as e:
    print(f"Error loading settings: {e}")
    print("Please ensure all required environment variables are set in .env file")
    raise

# Export commonly used values
APP_NAME = settings.app_name
VERSION = settings.version
ENVIRONMENT = settings.environment
DEBUG = settings.debug

# WordPress configuration
WORDPRESS_CONFIG = {
    'api_url': settings.wordpress_api_url,
    'username': settings.wordpress_username,
    'password': settings.wordpress_password,
    'timeout': settings.wordpress_timeout,
    'retry_attempts': settings.wordpress_retry_attempts
}

# LLM configuration
LLM_CONFIG = settings.get_llm_config()

# Directory paths
PATHS = {
    'output': settings.output_dir,
    'logs': settings.logs_dir,
    'temp': settings.temp_dir
}

# Feature flags
FEATURES = {
    'caching': settings.enable_caching,
    'metrics': settings.enable_metrics,
    'detailed_logs': settings.enable_detailed_logs,
    'preserve_media': settings.preserve_media,
    'preserve_links': settings.preserve_links,
    'seo_optimization': settings.seo_optimization,
    'auto_cleanup': settings.auto_cleanup_temp_files
}

# Processing limits
LIMITS = {
    'max_content_length': settings.max_content_length,
    'min_content_length': settings.min_content_length,
    'max_processing_time': settings.max_processing_time,
    'max_concurrent_sessions': settings.max_concurrent_sessions,
    'max_bulk_files': settings.max_bulk_files
}

# Export for easy importing
__all__ = [
    'settings',
    'Settings',
    'LoggingConfig',
    'APP_NAME',
    'VERSION',
    'ENVIRONMENT',
    'DEBUG',
    'WORDPRESS_CONFIG',
    'LLM_CONFIG',
    'PATHS',
    'FEATURES',
    'LIMITS'
]
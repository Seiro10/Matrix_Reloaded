import os
from app.config import settings


class FileUtils:
    """File utilities for handling temporary and generated files"""

    @staticmethod
    def save_temp_file(content: str, filename: str) -> str:
        """Save content to a temporary file"""
        os.makedirs(settings.temp_dir, exist_ok=True)
        filepath = os.path.join(settings.temp_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        return filepath

    @staticmethod
    def save_generated_file(content: str, filename: str) -> str:
        """Save content to the generated files directory"""
        os.makedirs(settings.generated_dir, exist_ok=True)
        filepath = os.path.join(settings.generated_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        return filepath

    @staticmethod
    def save_log_file(content: str, filename: str, subdir: str = "") -> str:
        """Save content to the logs directory"""
        log_dir = os.path.join(settings.logs_dir, subdir) if subdir else settings.logs_dir
        os.makedirs(log_dir, exist_ok=True)
        filepath = os.path.join(log_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        return filepath

    @staticmethod
    def read_file(filepath: str) -> str:
        """Read content from a file"""
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()

    @staticmethod
    def ensure_directories():
        """Ensure all required directories exist"""
        os.makedirs(settings.temp_dir, exist_ok=True)
        os.makedirs(settings.logs_dir, exist_ok=True)
        os.makedirs(settings.generated_dir, exist_ok=True)
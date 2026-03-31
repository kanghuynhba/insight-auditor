# src/core/config.py
import os
from functools import lru_cache
from pathlib import Path
from pydantic import SecretStr, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    Application settings. Pydantic will automatically load these from
    environment variables or a .env file.
    """
    # Azure OpenAI configuration 
    azure_openai_api_key: SecretStr
    azure_openai_endpoint: HttpUrl
    openai_api_version: str
    azure_deployment_name: str

    # Storage path
    chroma_db_path: Path = Path("./chroma_db")
    uploads_dir: Path = Path("./uploads")

    # Used by the Chunker in the IngestionService
    chunk_size: int = 1000
    chunk_overlap: int = 150

    # Application logic
    max_hints_per_chapter: int=5

    # Pydantic configuration
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

@lru_cache()
def get_settings() -> Settings:
    return Settings()

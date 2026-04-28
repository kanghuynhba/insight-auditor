# src/core/config.py
import os
from functools import lru_cache
from pathlib import Path

from pydantic import HttpUrl, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.infrastructure.llm.types import ModelConfig


class Settings(BaseSettings):
    """
    Application settings. Pydantic will automatically load these from
    environment variables or a .env file.
    """

    # Github models configuration
    github_endpoint: HttpUrl
    github_completion_api_key: SecretStr
    generative_model_name: str
    # api_version: str
    # registry_name: str
    # api_type: str
    # github_api_version: str = "2026-03-10"

    github_embedding_api_key: SecretStr
    embedding_model_name: str

    # # Azure OpenAI configuration
    # azure_openai_api_key: SecretStr
    # azure_openai_endpoint: HttpUrl
    # openai_api_version: str
    # generative_model_name: str
    # embedding_model_name: str
    # registry_name: str
    # api_type: str

    mariadb_url: str

    # Storage path
    lance_db_path: Path = Path("./lancedb")
    uploads_dir: Path = Path("./uploads")
    vector_index_name: str = "text_chunk"

    # Used by the Chunker in the IngestionService
    chunk_size: int = 800
    chunk_overlap: int = 200
    chunk_context_size: int = 1500

    # Application logic
    min_summary_words: int = 50
    max_hints_per_session: int = 5
    large_section_token_threshold: int = 4000

    # Hierarchy config
    deepest_level: int = 7

    # Pydantic configuration
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    @field_validator("mariadb_url")
    @classmethod
    def validate_mariadb_url(cls, v: str) -> str:
        """Ensures the async driver is specified for MariaDB."""
        if not v.startswith("mysql+aiomysql://"):
            raise ValueError(
                "mariadb_url must use the 'mysql+aiomysql://' scheme for async support."
            )
        return v

    @property
    def generative_model(self) -> ModelConfig:
        """
        Returns a dictionary formatted for litellm.completion()
        """
        return {
            "model": f"{self.generative_model_name}",
            "api_key": self.github_completion_api_key.get_secret_value(),
            "api_base": str(self.github_endpoint),
        }

    @property
    def embedding_model(self) -> ModelConfig:
        """
        Returns a dictionary formatted for litellm.embedding()
        """
        return {
            "model": f"{self.embedding_model_name}",
            "api_key": self.github_embedding_api_key.get_secret_value(),
            "api_base": str(self.github_endpoint),
        }


@lru_cache()
def get_settings() -> Settings:
    return Settings()

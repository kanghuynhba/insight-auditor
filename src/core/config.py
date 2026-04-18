# src/core/config.py
import os
from functools import lru_cache
from pathlib import Path

from pydantic import HttpUrl, SecretStr, field_validator
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
    generative_model: str
    embedding_model: str
    registry_name: str
    api_type: str

    # MariaDB / SQL Configuration
    # Example: mysql+aiomysql://user:password@localhost:3306/insight_auditor
    mariadb_url: str = "mysql+aiomysql://root:password@localhost:3306/insight_auditor"

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

    @field_validator("azure_openai_endpoint", mode="before")
    @classmethod
    def clean_openai_endpoint(cls, v: str) -> str:
        return str(v).split("/openai")[0].rstrip("/")

    @property
    def litellm_config(self) -> dict:
        """
        Returns a dictionary formatted for litellm.completion()
        """
        return {
            "model": f"azure/{self.generative_model}",
            "api_key": self.azure_openai_api_key.get_secret_value(),
            "base_url": str(self.azure_openai_endpoint),
            "api_version": self.openai_api_version,
        }


@lru_cache()
def get_settings() -> Settings:
    return Settings()

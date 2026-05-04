# src/infrastructure/llm/embedding/embedding.py

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Iterator
from typing import Any, Unpack

from src.infrastructure.llm.types import (
    LLMEmbeddingArgs,
    LLMEmbeddingResponse,
    ModelConfig,
    ResponseFormat,
)


class LLMEmbedding(ABC):
    """Abstract base class for language model Embeddings."""

    def __init__(
        self,
        config: ModelConfig,
        **kwargs: Any,
    ):
        """Initialize the LLMEmbedding"""
        self._config = config
        self._extra_kwargs = kwargs

    @abstractmethod
    def embed(
        self,
        /,
        **kwargs: Unpack["LLMEmbeddingArgs[ResponseFormat]"],
    ) -> "LLMEmbeddingResponse":
        """Sync Embedding method"""
        pass

    @abstractmethod
    async def async_embed(
        self,
        /,
        **kwargs: Unpack["LLMEmbeddingArgs[ResponseFormat]"],
    ) -> "LLMEmbeddingResponse":
        """Async Embedding method"""
        pass

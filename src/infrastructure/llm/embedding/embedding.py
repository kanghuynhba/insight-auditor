# src/infrastructure/llm/embedding/embedding.py

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Iterator
from typing import TYPE_CHECKING, Any, Unpack

if TYPE_CHECKING:
    from llm.types import (
        LLMEmbeddingArgs,
        LLMEmbeddingChunk,
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

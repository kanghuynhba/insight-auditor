# src/infrastructure/llm/embedding/embedding.py

from abc import ABC, abstractmethod


class LLMEmbedidng(ABC):
    """Abstract base class for language model embedding."""

    @abstractmethod
    def __init__(
        self,
        *,
        model: str,
        api_key: str | None = None,
        api_base: str | None = None,
        api_version: str | None = None,
        **kwargs: Any,
    ):
        """Initialize the LLMEmbedidng"""
        pass

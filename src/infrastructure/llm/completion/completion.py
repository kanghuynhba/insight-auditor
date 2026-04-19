# src/infrastructure/llm/completion/completion.py

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Iterator
from typing import TYPE_CHECKING, Any, Unpack

if TYPE_CHECKING:
    from llm.types import (
        LLMCompletionArgs,
        LLMCompletionChunk,
        LLMCompletionResponse,
        ModelConfig,
        ResponseFormat,
    )


class LLMCompletion(ABC):
    """Abstract base class for language model completions."""

    @abstractmethod
    def __init__(
        self,
        config: ModelConfig,
        **kwargs: Any,
    ):
        """Initialize the LLMCompletion"""
        self._config = config
        self._extra_kwargs = kwargs

    @abstractmethod
    def completion(
        self,
        /,
        **kwargs: Unpack["LLMCompletionArgs[ResponseFormat]"],
    ) -> "LLMCompletionResponse[ResponseFormat] | Iterator[LLMCompletionChunk]":
        """Sync completion method"""
        pass

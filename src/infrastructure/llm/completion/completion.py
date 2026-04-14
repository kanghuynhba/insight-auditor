# src/infrastructure/llm/completion/completion.py

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Iterator
from typing import TYPE_CHECKING, Any, Unpack

if TYPE_CHECKING:
    from llm.types import (LLMComlpetionChunk, LLMCompletionArgs,
                           LLMCompletionResponse, ResponseFormat)

class LLMCompletion(ABC):
    """Abstract base class for language model completions. """

    @abstractmethod
    def __init__(
        self,
        *,
        model: str,
        api_key: str | None = None,
        api_base: str | None = None,
        api_version: str | None = None,
        **kwargs: Any,
    )
    """Initialize the LLMCompletion"""

    raise NotImplementedError

    @abstractmethod
    def completion(
        self,
        /,
        **kwargs: Unpack["LLMCompletionArgs[ResponseFormat]"],
    ) -> "LLMCompletionResponse[ResponseFormat] | Iterator[LLMComlpetionChunk]"
        """Sync completion method"""

    raise NotImplementedError


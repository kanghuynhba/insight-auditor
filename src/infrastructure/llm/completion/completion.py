# src/infrastructure/llm/completion/completion.py

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Unpack

if TYPE_CHECKING:
    from llm.types import (
        LLMCompletionArgs,
        LLMCompletionResponse,
        ModelConfig,
        ResponseFormat,
    )


class LLMCompletion(ABC):
    """Abstract base class for language model completions."""

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
    ) -> LLMCompletionResponse:
        """Sync completion method"""
        pass

    @abstractmethod
    async def async_completion(
        self,
        /,
        **kwargs: Unpack[LLMCompletionArgs[ResponseFormat]],
    ) -> LLMCompletionResponse[ResponseFormat]:
        """
        Asynchronous completion call with automatic normalization.
        """
        pass

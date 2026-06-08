# src/llm/_embedding.py

import logging
from typing import Any, Unpack

import litellm
from src.llm._types import (
    LLMEmbeddingArgs,
    LLMEmbeddingResponse,
    ModelConfig,
)

logger = logging.getLogger(__name__)


class LiteLLMEmbedding:
    """
    Standardized LiteLLM embedding engine.
    Connects to various providers via LiteLLM's unified embedding interface.
    """

    def __init__(
        self,
        config: ModelConfig,
        **kwargs: Any,
    ) -> None:
        self._config = config
        self._extra_kwargs = kwargs

    def embed(
        self,
        /,
        **kwargs: Unpack[LLMEmbeddingArgs],
    ) -> LLMEmbeddingResponse:
        """
        Synchronous embedding call.
        """
        payload = self._build_args(**kwargs)

        try:
            raw_response = litellm.embedding(**payload)

            # Use the model_dump to populate your Pydantic LLMEmbeddingResponse
            return LLMEmbeddingResponse(**raw_response.model_dump())

        except Exception as e:
            logger.error(f"LiteLLM embedding call failed: {str(e)}")
            raise

    async def async_embed(
        self,
        /,
        **kwargs: Unpack[LLMEmbeddingArgs],
    ) -> LLMEmbeddingResponse:
        """
        Asynchronous embedding call.
        """
        payload = self._build_args(**kwargs)

        try:
            # Notice the use of aembedding instead of embedding
            raw_response = await litellm.aembedding(**payload)

            return LLMEmbeddingResponse(**raw_response.model_dump())

        except Exception as e:
            logger.error(f"LiteLLM async embedding call failed: {str(e)}")
            raise

    def _build_args(self, **kwargs: Any) -> dict[str, Any]:
        """
        Assembles the LiteLLM-compatible dictionary for embeddings.
        """
        return {
            **self._config,
            **self._extra_kwargs,
            **kwargs,
        }

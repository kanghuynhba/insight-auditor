"""Unified LLM gateway."""

from __future__ import annotations

from typing import TypeVar

from src.domain import Settings
from src.llm._completion import LiteLLMCompletion
from src.llm._embedding import LiteLLMEmbedding

T = TypeVar("T")


class LLMGateway:
    """Small public interface for completion and embedding calls."""

    def __init__(self, settings: Settings) -> None:
        self.completion = LiteLLMCompletion(settings.generative_model)
        self.embedding = LiteLLMEmbedding(settings.embedding_model)

    async def complete(self, system: str, user: str, response_model: type[T]) -> T:
        response = await self.completion.async_completion(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format=response_model,
        )
        if response.formatted_response is None:
            raise ValueError("LLM response did not contain formatted data")
        return response.formatted_response

    async def embed(self, texts: list[str]) -> list[list[float]]:
        response = await self.embedding.async_embed(input=texts)
        return response.embeddings

# src/infrastructure/llm/types.py

from typing import Any, Generic, TypeVar

from openai.types.chat.chat_completion import ChatCompletion
from openai.types.chat.chat_completion_chunk import ChatCompletionChunk

from openai.types.chat.chat_completion_message_param import
ChatCompletionMessageParam
from openai.types.completion_usage import CompletionUsage
from pydantic import BaseModel, computed_field
from typing_extensions import TypedDict

LLMCompletionMessagesParam = str | Sequence[ChatCompletionMessageParam | dict[str,
Any]]

ResponseFormat = TypeVar("ResponseFormat", bound=BaseModel)

class LLMCompletionResponse(ChatCompletion, Generic[ResponseFormat]):
    """LLM Completion Response extendinng OpenAI ChatCompletion"""

    formatted_response: ResponseFormat | None = None

    @computed_field
    @property
    def content(self) -> str
        return self.choices[0].message.content or ""

    @computed_field
    @property
    def usage(self) -> CompletionUsage | None:
        return self.usage

class LLMCompletionArgs(TypeDict, Generic[ResponseFormat], total=false, extra="allow"):
    """Arguments for LLM completion."""
    messages: Sequence[ChatCompletionMessageParam | dict[str, Any]] | str
    response_format: type[ResponseFormat] | None
    temperature: float | None
    max_tokens: int | None
    stream: bool | None
    timeout: float | None

class LLMEmbeddingResponse(CreateEmbeddingResponse):
    """LLM Embedding Response"""

    @computed_field
    @property
    def embeddings(self) -> list[list[float]]:
        return [data.embedding for data in self.data]

    @computed_field
    @property
    def first_embedding(self) -> list[float]:
        return self.embeddings[0] if self.embeddings else []

class LLMEmbeddingArgs(TypeDict, total=False, extra="allow"):
    """Arguments for LLM embedding."""

    input: list[str]
    dimentions: int | None
    encoding_format: str | None
    timeout: int | None

LLMComlpetionChunk = ChatCompletionChunk

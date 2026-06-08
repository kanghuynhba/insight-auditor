# src/llm/_types.py

from typing import Any, Generic, List, Optional, Sequence, TypeVar

from openai.types import CreateEmbeddingResponse
from openai.types.chat.chat_completion_chunk import ChatCompletionChunk
from openai.types.chat.chat_completion_message_param import ChatCompletionMessageParam
from openai.types.completion_usage import CompletionUsage
from pydantic import BaseModel, Field, computed_field
from typing_extensions import NotRequired, TypedDict

LLMCompletionMessagesParam = str | Sequence[ChatCompletionMessageParam | dict[str, Any]]

ResponseFormat = TypeVar("ResponseFormat", bound=object)


class ModelConfig(TypedDict):
    model: str
    api_key: str
    api_base: str
    api_version: NotRequired[str]
    timeout: NotRequired[float]
    max_retries: NotRequired[int]


class LLMCompletionResponse(BaseModel, Generic[ResponseFormat]):
    """Simplified LLM completion response."""

    id: str = ""
    choices: List[Any] = Field(default_factory=list)
    usage: Optional[CompletionUsage] = None
    formatted_response: ResponseFormat | None = None

    @computed_field
    @property
    def content(self) -> str:
        if self.choices and len(self.choices) > 0:
            first_choice = self.choices[0]
            if isinstance(first_choice, dict):
                message = first_choice.get("message", {})
                return message.get("content", "") if isinstance(message, dict) else ""
            else:
                message = getattr(first_choice, "message", None)
                return getattr(message, "content", "") if message else ""
        return ""


class LLMCompletionArgs(TypedDict, Generic[ResponseFormat], total=False):
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


class LLMEmbeddingArgs(TypedDict, total=False):
    """Arguments for LLM embedding."""

    input: list[str]
    dimensions: int | None
    encoding_format: str | None
    timeout: int | None


LLMCompletionChunk = ChatCompletionChunk

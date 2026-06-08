# src/llm/_completion.py

import logging
from typing import Any, Unpack

import litellm
from src.llm._types import (
    LLMCompletionArgs,
    LLMCompletionMessagesParam,
    LLMCompletionResponse,
    ModelConfig,
    ResponseFormat,
)

# Suppress noisy debug logs for a cleaner terminal
litellm.suppress_debug_info = True
logger = logging.getLogger(__name__)


class LiteLLMCompletion:
    """
    Standardized LiteLLM engine for the Insight Auditor.
    Wraps provider-specific details (Azure/OpenAI) into a unified interface.
    """

    def __init__(
        self,
        config: ModelConfig,
        **kwargs: Any,
    ) -> None:
        self._config = config
        self._extra_kwargs = kwargs

    def completion(
        self,
        /,
        **kwargs: Unpack[LLMCompletionArgs[ResponseFormat]],
    ) -> LLMCompletionResponse[ResponseFormat]:
        """
        Synchronous completion call with automatic normalization.
        """
        messages: LLMCompletionMessagesParam = kwargs.pop("messages")
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]

        response_format = kwargs.pop("response_format", None)

        payload = self._build_args(messages, response_format, **kwargs)

        try:
            raw_response = litellm.completion(**payload)

            llm_response = LLMCompletionResponse(**raw_response.model_dump())

            if response_format is not None and llm_response.content:
                llm_response.formatted_response = self._parse_json(
                    llm_response.content, response_format
                )

            return llm_response

        except Exception as e:
            logger.error(f"LiteLLM call failed: {str(e)}")
            raise

    async def async_completion(
        self,
        /,
        **kwargs: Unpack[LLMCompletionArgs[ResponseFormat]],
    ) -> LLMCompletionResponse[ResponseFormat]:
        """
        Asynchronous completion call with automatic normalization.
        """
        messages: LLMCompletionMessagesParam = kwargs.pop("messages")
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]

        response_format = kwargs.pop("response_format", None)
        payload = self._build_args(messages, response_format, **kwargs)

        try:
            # CRITICAL: Use litellm.acompletion (with an 'a')
            raw_response = await litellm.acompletion(**payload)

            llm_response = LLMCompletionResponse(**raw_response.model_dump())

            if response_format is not None and llm_response.content:
                llm_response.formatted_response = self._parse_json(
                    llm_response.content, response_format
                )

            return llm_response

        except Exception as e:
            logger.error(f"LiteLLM async call failed: {str(e)}")
            raise

    def _build_args(
        self,
        messages: LLMCompletionMessagesParam,
        response_format: type[ResponseFormat] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Assembles the LiteLLM-compatible dictionary.
        """
        args = {**self._config, **self._extra_kwargs, **kwargs, "messages": messages}

        if response_format is not None:
            # if (
            #     not hasattr(response_format, "__origin__")
            #     or response_format.__origin__ != list
            # ):
            args["response_format"] = {"type": "json_object"}

        return args

    # TODO: move this out into some helpers that supports json processing

    @staticmethod
    def _parse_json(
        content: str, response_format: type[ResponseFormat]
    ) -> ResponseFormat:
        """
        Parses the raw string content into the requested format.
        Supports Pydantic models, list[T], and dict.
        """
        import json

        try:
            # Strip markdown fences
            clean_content = content.strip()
            if clean_content.startswith("```json"):
                clean_content = clean_content[7:]  # length of ```json
            elif clean_content.startswith("```"):
                clean_content = clean_content[3:]

            if clean_content.endswith("```"):
                clean_content = clean_content[:-3]

            clean_content = clean_content.strip()
            data = json.loads(clean_content)

            # Check if the expected type is a list
            origin = getattr(response_format, "__origin__", None)
            if origin is list:
                if isinstance(data, list):
                    return data
                if isinstance(data, dict) and isinstance(data.get("facts"), list):
                    return data["facts"]
                raise ValueError("expected a list or {'facts': [...]}")

            # For non-list expected types (Pydantic model, etc.)
            if hasattr(response_format, "model_validate"):
                return response_format.model_validate(data)

            return data

        except Exception as e:
            name = getattr(response_format, "__name__", repr(response_format))
            raise ValueError(f"Failed to parse LLM response into {name}: {e}") from e

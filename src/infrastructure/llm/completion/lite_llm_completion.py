# src/infrastructure/llm/completion/lite_llm_completion.py

import logging
from typing import Any, Unpack

import litellm
from src.infrastructure.llm.completion.completion import LLMCompletion
from src.infrastructure.llm.types import (
    LLMCompletionArgs,
    LLMCompletionMessagesParam,
    LLMCompletionResponse,
    ModelConfig,
    ResponseFormat,
)

# Suppress noisy debug logs for a cleaner terminal
litellm.suppress_debug_info = True
logger = logging.getLogger(__name__)


class LiteLLMCompletion(LLMCompletion):
    """
    Standardized LiteLLM engine for the Insight Auditor.
    Wraps provider-specific details (Azure/OpenAI) into a unified interface.
    """

    def __init__(
        self,
        config: ModelConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(config, **kwargs)

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
        If a list is expected but a dict is parsed:
            - If the dict has fact-like keys (point, rank, etc.), wrap it in a list.
            - Otherwise, try to extract a list from common keys like "facts", "result", etc.
        """
        import json
        import logging

        logger = logging.getLogger(__name__)

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
                # Expected a list, but got a dict
                if isinstance(data, dict):
                    # If it looks like a single fact (has point/rank keys), wrap it
                    if "point" in data or "rank" in data:
                        logger.debug("Wrapping single fact dict into list")
                        return [data]
                    # Otherwise try to extract list from common keys
                    for key in ["facts", "result", "data", "items", "atomic_facts"]:
                        if key in data and isinstance(data[key], list):
                            logger.debug(f"Extracted list from dict key '{key}'")
                            return data[key]
                    # No suitable list found
                    logger.warning(
                        f"Expected list but got dict with keys {list(data.keys())}; returning empty list"
                    )
                    return []
                # Already a list, return as is
                return data

            # For non-list expected types (Pydantic model, etc.)
            if hasattr(response_format, "model_validate"):
                return response_format.model_validate(data)

            return data

        except Exception as e:
            name = getattr(response_format, "__name__", repr(response_format))
            raise ValueError(f"Failed to parse LLM response into {name}: {e}") from e

# src/infrastructure/llm/completion/lite_llm_completion.py

import logging
from typing import Any, Unpack

import litellm
from src.llm.completion.base import LLMCompletion
from src.llm.types import (
    LLMCompletionArgs,
    LLMCompletionMessagesParam,
    LLMCompletionResponse,
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
        *,
        model: str,
        api_key: str | None = None,
        api_base: str | None = None,
        api_version: str | None = None,
        **kwargs: Any,
    ) -> None:
        self._model = model
        self._api_key = api_key
        self._api_base = api_base
        self._api_version = api_version
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

    def _build_args(
        self,
        messages: LLMCompletionMessagesParam,
        response_format: type[ResponseFormat] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Assembles the LiteLLM-compatible dictionary.
        """
        args = {
            "model": self._model,
            "messages": messages,
            "api_key": self._api_key,
            "api_base": self._api_base,
            "api_version": self._api_version,
            "num_retries": 3,
            **self._extra_kwargs,
            **kwargs,
        }

        if response_format is not None:
            args["response_format"] = {"type": "json_object"}[cite:57]

        return args

    @staticmethod
    def _parse_json(
        content: str, response_format: type[ResponseFormat]
    ) -> ResponseFormat:
        """
        Parses the raw string content into the requested Pydantic model.
        """
        import json

        try:
            # Clean up potential markdown fences if the LLM adds them
            clean_content = content.strip().removeprefix("```json").removesuffix("```")
            data = json.loads(clean_content)
            return response_format.model_validate(data)
        except Exception as e:
            raise ValueError(
                f"Failed to parse LLM response into {response_format.__name__}: {e}"
            )

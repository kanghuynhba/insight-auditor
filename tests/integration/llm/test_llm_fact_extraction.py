# tests/integration/llm/test_llm_fact_extraction.py

from typing import Any, Dict, List
from unittest.mock import AsyncMock, Mock, patch

import pytest
from src.core.atomic_fact import AtomicFact
from src.core.enums import Tier
from src.index.operations.extract_atomic_facts import extract_atomic_facts
from src.infrastructure.prompts.index.extract_atomic_facts import (
    ATOMIC_FACT_SYSTEM,
    ATOMIC_FACT_USER,
)


class MockLLMResponse:
    """Mock LLM response object with formatted_response attribute."""

    def __init__(self, formatted_response):
        self.formatted_response = formatted_response


class TestLLMFactExtraction:
    """Test LLM integration for atomic fact extraction."""

    @pytest.fixture
    def mock_llm_completion(self):
        """Create a mock LLM completion client."""
        mock = Mock()
        mock.completion = Mock()
        return mock

    @pytest.fixture
    def sample_success_response(self):
        """Sample successful LLM response."""
        return MockLLMResponse(
            [
                {
                    "point": "Python is an interpreted, high-level programming language",
                    "rank": 1,
                    "reason": "Core definition of Python's execution model",
                },
                {
                    "point": "Python supports multiple programming paradigms including object-oriented and functional programming",
                    "rank": 2,
                    "reason": "Key language characteristic",
                },
                {
                    "point": "Python's dynamic typing allows variables to change type at runtime",
                    "rank": 3,
                    "reason": "Nuanced feature of the language",
                },
            ]
        )

    @pytest.fixture
    def sample_text(self):
        """Sample text for extraction."""
        return """
        Python is an interpreted, high-level programming language. 
        It supports multiple programming paradigms, including object-oriented, 
        imperative, and functional programming. Python features dynamic typing 
        and automatic memory management.
        """

    def test_extract_atomic_facts_success(
        self, mock_llm_completion, sample_success_response, sample_text
    ):
        """Test successful extraction of atomic facts from LLM."""
        mock_llm_completion.completion.return_value = sample_success_response

        facts = extract_atomic_facts(
            model=mock_llm_completion,
            system_prompt=ATOMIC_FACT_SYSTEM,
            user_prompt_template=ATOMIC_FACT_USER,
            text=sample_text,
            path_id="001.002",
            section_id="test-section-001",
        )

        assert len(facts) == 3
        assert all(isinstance(fact, AtomicFact) for fact in facts)
        assert facts[0].rank == Tier.CRITICAL
        assert facts[1].rank == Tier.IMPORTANT
        assert facts[2].rank == Tier.NUANCE

    def test_extract_atomic_facts_empty_response(
        self, mock_llm_completion, sample_text
    ):
        """Test handling of empty response from LLM."""
        mock_llm_completion.completion.return_value = MockLLMResponse(None)

        facts = extract_atomic_facts(
            model=mock_llm_completion,
            system_prompt=ATOMIC_FACT_SYSTEM,
            user_prompt_template=ATOMIC_FACT_USER,
            text=sample_text,
            path_id="001.002",
            section_id="test-section-001",
        )

        assert facts == []

    def test_extract_atomic_facts_invalid_response_type(
        self, mock_llm_completion, sample_text, caplog
    ):
        """Test handling of invalid response type from LLM."""
        mock_llm_completion.completion.return_value = MockLLMResponse("not a list")

        facts = extract_atomic_facts(
            model=mock_llm_completion,
            system_prompt=ATOMIC_FACT_SYSTEM,
            user_prompt_template=ATOMIC_FACT_USER,
            text=sample_text,
            path_id="001.002",
            section_id="test-section-001",
        )

        assert facts == []

    def test_extract_atomic_facts_missing_fields(
        self, mock_llm_completion, sample_text
    ):
        """Test extraction when LLM returns facts with missing fields."""
        response = MockLLMResponse(
            [
                {
                    "point": "Only point provided",
                    # Missing rank and reason
                }
            ]
        )
        mock_llm_completion.completion.return_value = response

        facts = extract_atomic_facts(
            model=mock_llm_completion,
            system_prompt=ATOMIC_FACT_SYSTEM,
            user_prompt_template=ATOMIC_FACT_USER,
            text=sample_text,
            path_id="001.002",
            section_id="test-section-001",
        )

        assert len(facts) == 1
        assert facts[0].point == "Only point provided"
        assert facts[0].rank == Tier.NUANCE  # Default
        assert facts[0].reason == ""  # Default empty string

    def test_extract_atomic_facts_llm_error(self, mock_llm_completion, sample_text):
        """Test handling of LLM API errors."""
        mock_llm_completion.completion.side_effect = Exception("API Error")

        with pytest.raises(Exception):
            extract_atomic_facts(
                model=mock_llm_completion,
                system_prompt=ATOMIC_FACT_SYSTEM,
                user_prompt_template=ATOMIC_FACT_USER,
                text=sample_text,
                path_id="001.002",
                section_id="test-section-001",
            )

    def test_extract_atomic_facts_prompt_formatting(
        self, mock_llm_completion, sample_success_response
    ):
        """Test that prompts are properly formatted with text and path_id."""
        mock_llm_completion.completion.return_value = sample_success_response

        test_text = "Custom test text"
        test_path_id = "999.888"

        extract_atomic_facts(
            model=mock_llm_completion,
            system_prompt=ATOMIC_FACT_SYSTEM,
            user_prompt_template=ATOMIC_FACT_USER,
            text=test_text,
            path_id=test_path_id,
            section_id="test-section",
        )

        call_args = mock_llm_completion.completion.call_args
        messages = call_args.kwargs["messages"]

        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == ATOMIC_FACT_SYSTEM

        user_message = messages[1]["content"]
        assert test_text in user_message
        assert test_path_id in user_message

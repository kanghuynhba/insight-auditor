# tests/unit/indexing/test_atomic_fact_logic.py

from typing import Any, Dict
from unittest.mock import Mock, patch

import pytest
from src.core.atomic_fact import AtomicFact
from src.core.enums import Tier
from src.index.operations.extract_atomic_facts import extract_atomic_facts


class MockLLMResponse:
    """Mock LLM response object with formatted_response attribute."""

    def __init__(self, formatted_response):
        self.formatted_response = formatted_response


class TestFactExtractionLogic:
    """Unit tests for fact extraction logic (without real LLM)."""

    def create_mock_response(self, facts_data: list) -> MockLLMResponse:
        """Helper to create mock LLM response with proper structure."""
        return MockLLMResponse(formatted_response=facts_data)

    def test_extraction_handles_different_rank_formats(self):
        """Test that extraction handles various rank formats correctly."""
        mock_llm = Mock()

        # Updated test cases to match the correct mapping:
        # 1 → Tier.CRITICAL, 2 → Tier.IMPORTANT, 3 → Tier.NUANCE
        test_cases = [
            (3, Tier.NUANCE),  # was (3, Tier.CRITICAL)
            (2, Tier.IMPORTANT),
            (1, Tier.CRITICAL),  # was (1, Tier.NUANCE)
            ("CRITICAL", Tier.CRITICAL),
            ("IMPORTANT", Tier.IMPORTANT),
            ("NUANCE", Tier.NUANCE),
            (None, Tier.NUANCE),
            ("invalid", Tier.NUANCE),
        ]

        for rank_input, expected_tier in test_cases:
            mock_response = self.create_mock_response(
                [{"point": "Test point", "rank": rank_input, "reason": "Test reason"}]
            )
            mock_llm.completion.return_value = mock_response

            facts = extract_atomic_facts(
                model=mock_llm,
                system_prompt="system",
                user_prompt_template="{text} {path_id}",
                text="test",
                path_id="001",
                section_id="sec-001",
            )

            assert len(facts) == 1
            assert facts[0].rank == expected_tier

    def test_extraction_injects_correct_ids(self):
        """Test that extraction correctly injects section_id and path_id."""
        mock_llm = Mock()
        mock_response = self.create_mock_response(
            [
                {"point": "Fact 1", "rank": 3, "reason": "Reason 1"},
                {"point": "Fact 2", "rank": 2, "reason": "Reason 2"},
            ]
        )
        mock_llm.completion.return_value = mock_response

        test_section_id = "custom-section-123"
        test_path_id = "custom-path-456"

        facts = extract_atomic_facts(
            model=mock_llm,
            system_prompt="system",
            user_prompt_template="{text} {path_id}",
            text="test",
            path_id=test_path_id,
            section_id=test_section_id,
        )

        for fact in facts:
            assert fact.section_id == test_section_id
            assert fact.path_id == test_path_id

    def test_extraction_preserves_fact_order(self):
        """Test that extracted facts maintain the order from LLM response."""
        mock_llm = Mock()
        expected_points = ["First fact", "Second fact", "Third fact"]

        mock_response = self.create_mock_response(
            [
                {"point": p, "rank": 1, "reason": f"Reason for {p}"}
                for p in expected_points
            ]
        )
        mock_llm.completion.return_value = mock_response

        facts = extract_atomic_facts(
            model=mock_llm,
            system_prompt="system",
            user_prompt_template="{text} {path_id}",
            text="test",
            path_id="001",
            section_id="sec-001",
        )

        for i, fact in enumerate(facts):
            assert fact.point == expected_points[i]

    def test_extraction_handles_empty_facts_list(self):
        """Test extraction handles empty facts list from LLM."""
        mock_llm = Mock()
        mock_response = self.create_mock_response([])
        mock_llm.completion.return_value = mock_response

        facts = extract_atomic_facts(
            model=mock_llm,
            system_prompt="system",
            user_prompt_template="{text} {path_id}",
            text="test",
            path_id="001",
            section_id="sec-001",
        )

        assert facts == []

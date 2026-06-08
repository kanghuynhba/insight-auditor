from unittest.mock import AsyncMock

import pytest
from src.domain.enums import Tier
from src.domain.text_chunk import TextChunk
from src.extraction._parser import extract_facts


class MockLLMResponse:
    def __init__(self, formatted_response):
        self.formatted_response = formatted_response


class TestFactExtractionLogic:
    def create_mock_response(self, facts_data: list) -> MockLLMResponse:
        return MockLLMResponse(formatted_response=facts_data)

    def create_chunk(self) -> TextChunk:
        return TextChunk(
            id="chunk-001",
            book_id="book-001",
            section_id="sec-001",
            text="[Book > Section]\ntest",
            chunk_index=0,
            chunk_level="sentence",
            start_char=10,
            end_char=14,
        )

    @pytest.mark.asyncio
    async def test_extraction_handles_different_rank_formats(self):
        mock_llm = AsyncMock()

        test_cases = [
            (3, Tier.NUANCE),
            (2, Tier.IMPORTANT),
            (1, Tier.CRITICAL),
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
            mock_llm.async_completion.return_value = mock_response

            facts = await extract_facts(
                chunk=self.create_chunk(),
                llm=mock_llm,
                system_prompt="system",
                user_prompt_template="{body_text} {max_facts} {chunk_token_count}",
            )

            assert len(facts) == 1
            assert facts[0].rank == expected_tier

    @pytest.mark.asyncio
    async def test_extraction_injects_correct_ids(self):
        mock_llm = AsyncMock()
        mock_response = self.create_mock_response(
            [
                {"point": "Fact 1", "rank": 3, "reason": "Reason 1"},
                {"point": "Fact 2", "rank": 2, "reason": "Reason 2"},
            ]
        )
        mock_llm.async_completion.return_value = mock_response

        test_section_id = "custom-section-123"
        test_chunk_id = "custom-chunk-456"
        chunk = self.create_chunk().model_copy(
            update={"id": test_chunk_id, "section_id": test_section_id}
        )

        facts = await extract_facts(
            chunk=chunk,
            llm=mock_llm,
            system_prompt="system",
            user_prompt_template="{body_text} {max_facts} {chunk_token_count}",
        )

        for fact in facts:
            assert fact.section_id == test_section_id
            assert fact.chunk_id == test_chunk_id

    @pytest.mark.asyncio
    async def test_extraction_preserves_fact_order(self):
        mock_llm = AsyncMock()
        expected_points = ["First fact", "Second fact", "Third fact"]

        mock_response = self.create_mock_response(
            [
                {"point": p, "rank": 1, "reason": f"Reason for {p}"}
                for p in expected_points
            ]
        )
        mock_llm.async_completion.return_value = mock_response

        facts = await extract_facts(
            chunk=self.create_chunk(),
            llm=mock_llm,
            system_prompt="system",
            user_prompt_template="{body_text} {max_facts} {chunk_token_count}",
        )

        for i, fact in enumerate(facts):
            assert fact.point == expected_points[i]

    @pytest.mark.asyncio
    async def test_extraction_handles_empty_facts_list(self):
        mock_llm = AsyncMock()
        mock_response = self.create_mock_response([])
        mock_llm.async_completion.return_value = mock_response

        facts = await extract_facts(
            chunk=self.create_chunk(),
            llm=mock_llm,
            system_prompt="system",
            user_prompt_template="{body_text} {max_facts} {chunk_token_count}",
        )

        assert facts == []

    @pytest.mark.asyncio
    async def test_extraction_accepts_explicit_facts_wrapper(self):
        mock_llm = AsyncMock()
        mock_response = MockLLMResponse(
            formatted_response={
                "facts": [
                    {
                        "point": "Wrapped fact",
                        "rank": 1,
                        "reason": "Explicit facts wrapper",
                    }
                ]
            }
        )
        mock_llm.async_completion.return_value = mock_response

        facts = await extract_facts(
            chunk=self.create_chunk(),
            llm=mock_llm,
            system_prompt="system",
            user_prompt_template="{body_text} {max_facts} {chunk_token_count}",
        )

        assert len(facts) == 1
        assert facts[0].point == "Wrapped fact"

    @pytest.mark.asyncio
    async def test_extraction_rejects_generic_wrapper_keys(self):
        mock_llm = AsyncMock()
        mock_response = MockLLMResponse(formatted_response={"data": []})
        mock_llm.async_completion.return_value = mock_response

        with pytest.raises(ValueError, match="facts"):
            await extract_facts(
                chunk=self.create_chunk(),
                llm=mock_llm,
                system_prompt="system",
                user_prompt_template="{body_text} {max_facts} {chunk_token_count}",
            )

    @pytest.mark.asyncio
    async def test_extraction_rejects_non_object_fact_items(self):
        mock_llm = AsyncMock()
        mock_response = MockLLMResponse(formatted_response=["not-a-fact"])
        mock_llm.async_completion.return_value = mock_response

        with pytest.raises(ValueError, match="objects"):
            await extract_facts(
                chunk=self.create_chunk(),
                llm=mock_llm,
                system_prompt="system",
                user_prompt_template="{body_text} {max_facts} {chunk_token_count}",
            )

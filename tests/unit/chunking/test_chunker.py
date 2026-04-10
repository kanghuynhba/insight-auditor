# Copyright (c) 2024 Your Company.
# Licensed under the MIT License

from typing import Any

import pytest
from src.core.config import Settings, get_settings
from src.infrastructure.chunking.natural_boundary_chunker import NaturalBoundaryChunker
from src.infrastructure.chunking.text_chunk import TextChunk


class TestNaturalBoundaryChunker:
    """Test suite for the NaturalBoundaryChunker, verifying text splitting, overlap, and context."""

    def setup_method(self, method: Any) -> None:
        """Setup common test variables before each test runs."""
        self.section_id = "test_sec_001"
        self.book_id = "test_book_001"
        self.path_id = "001.002"

    def test_basic_sentence_accumulation(self):
        """Test that sentences accumulate until max tokens is hit, without cutting mid-sentence."""
        input_text = "This is the first sentence. This is the second. And the third."

        # We set chunk_size=12.
        # _tokens math: 5 words * 1.3 = 6 tokens per sentence.
        # Sentences 1 & 2 = 12 tokens (Fits). Sentence 3 pushes it over.
        settings = Settings(chunk_size=12, chunk_overlap=0, chunk_context_size=50)
        chunker = NaturalBoundaryChunker(settings)
        chunks = chunker.chunk_section(
            self.section_id, self.book_id, self.path_id, input_text
        )

        assert len(chunks) == 2

        assert chunks[0].text == "This is the first sentence. This is the second."
        assert chunks[0].chunk_index == 0
        assert chunks[0].chunk_level == "sentence"

        assert chunks[1].text == "And the third."
        assert chunks[1].chunk_index == 1

    def test_overlap_tail_generation(self):
        """Test that the overlap budget correctly pulls preceding sentences."""
        input_text = "Sentence one. Sentence two. Sentence three. Sentence four."

        settings = Settings(
            chunk_size=4,  # Force 2 sentences per chunk
            chunk_overlap=2,  # Overlap budget allows ~1 sentence to trail backward
            chunk_context_size=50,
        )
        chunker = NaturalBoundaryChunker(settings)
        chunks = chunker.chunk_section(
            self.section_id, self.book_id, self.path_id, input_text
        )

        assert len(chunks) == 2

        # First chunk has no overlap to pull from
        assert chunks[0].text == "Sentence one. Sentence two."

        # Second chunk should prepend "Sentence two." due to the overlap budget
        assert chunks[1].text == "Sentence two. Sentence three. Sentence four."

    def test_context_window_expansion(self):
        """Test that the context_text expands outward to adjacent chunks."""
        input_text = "A. B. C. D. E."

        settings = Settings(
            chunk_size=1,  # Forces 1 sentence per chunk roughly
            chunk_overlap=0,
            chunk_context_size=15,  # Big enough to grab neighbors
        )
        chunker = NaturalBoundaryChunker(settings)
        chunks = chunker.chunk_section(
            self.section_id, self.book_id, self.path_id, input_text
        )

        assert len(chunks) == 5

        # Chunk 2's tight text is just "C."
        assert chunks[2].text == "C."

        # Its context window should expand to include "B." and "D."
        # Because we alternate left/right in _build_context_windows
        assert "B. C. D." in chunks[2].context_text

        # Ensure the edges expand properly too (Chunk 0 only has right neighbors)
        assert "A. B. C." in chunks[0].context_text

    def test_word_window_fallback(self):
        """Test that an aggressively long run-on sentence falls back to word windows."""
        # 16 words. 16 * 1.3 = ~20 tokens.
        input_text = "This is a massive run on sentence that never ends and just keeps going and going."

        settings = Settings(
            chunk_size=10,  # Force it to break mid-sentence
            chunk_overlap=0,
            chunk_context_size=50,
        )
        chunker = NaturalBoundaryChunker(settings)
        chunks = chunker.chunk_section(
            self.section_id, self.book_id, self.path_id, input_text
        )

        assert len(chunks) > 1
        assert chunks[0].chunk_level == "word_window"
        # The step is max_tokens, so chunk 0 gets the first 10 words
        assert chunks[0].text == "This is a massive run on sentence that never ends"
        assert chunks[1].text == "and just keeps going and going."

    def test_cleaning_and_whitespace_normalization(self):
        """Test that PDF artifacts (hyphens, form feeds, blank lines) are cleaned."""
        input_text = (
            "Here is a bro-\nken word. \f  Lots of spaces.   \n\n\n\nToo many newlines."
        )

        settings = Settings(chunk_size=50, chunk_overlap=0, chunk_context_size=100)
        chunker = NaturalBoundaryChunker(settings)

        # We can test the private cleaner directly just like the original tests
        cleaned = chunker._clean(input_text)

        assert "broken word" in cleaned
        assert "\f" not in cleaned
        assert "Lots of spaces." in cleaned
        assert "\n\n\n" not in cleaned
        assert "\n\n" in cleaned  # Max 2 newlines retained

    def test_empty_or_whitespace_input(self):
        """Test that empty inputs are handled gracefully."""
        settings = Settings(chunk_size=10, chunk_overlap=0, chunk_context_size=10)
        chunker = NaturalBoundaryChunker(settings)

        assert (
            chunker.chunk_section(self.section_id, self.book_id, self.path_id, "") == []
        )
        assert (
            chunker.chunk_section(
                self.section_id, self.book_id, self.path_id, "   \n  \t  "
            )
            == []
        )


def test_chunker_produces_output():
    settings = get_settings()
    chunker = NaturalBoundaryChunker(settings)

    # Use the same text length as your real sections (~2800 chars)
    sample_text = (
        "This is a test sentence about distributed systems. " * 60
    )  # ~3000 chars

    chunks = chunker.chunk_section(
        section_id="test-section-id",
        book_id="test-book-id",
        path_id="003.001",
        text=sample_text,
    )

    print(f"\nchunk_size setting:    {settings.chunk_size}")
    print(f"chunk_overlap setting: {settings.chunk_overlap}")
    print(f"Chunks produced:       {len(chunks)}")
    if chunks:
        print(f"First chunk text_len:  {len(chunks[0].text)}")

    assert len(chunks) > 0, (
        f"Chunker returned empty list for {len(sample_text)}-char input. "
        f"chunk_size={settings.chunk_size}, overlap={settings.chunk_overlap}"
    )

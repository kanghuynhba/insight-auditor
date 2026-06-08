# Copyright (c) 2024 Your Company.
# Licensed under the MIT License

from typing import Any

import pytest
from src.domain.config import Settings, get_settings
from src.domain.section import Section
from src.ingestion._chunking import ChunkContext, NaturalBoundaryChunker


class TestNaturalBoundaryChunker:
    def setup_method(self, method: Any) -> None:
        self.section_id = "test_sec_001"
        self.book_id = "test_book_001"
        self.path_id = "001.002"

    def make_section(self, text: str, title: str = "Test Section") -> Section:
        section = Section(
            id=self.section_id,
            book_id=self.book_id,
            title=title,
            raw_text=text,
            extraction_status="NONE",
        )
        return section

    def make_context(self, section_title: str = "Test Section") -> ChunkContext:
        return ChunkContext(
            book_id=self.book_id,
            book_title="Test Book",
            chapter_title="Chapter 1",
            section_title=section_title,
        )

    @staticmethod
    def chunk_body(chunk) -> str:
        return chunk.text.split("\n", 1)[1]

    def test_basic_sentence_accumulation(self):
        input_text = "This is the first sentence. This is the second. And the third."

        settings = Settings(chunk_size=12, chunk_overlap=0, chunk_context_size=50)
        chunker = NaturalBoundaryChunker(settings)
        section = self.make_section(input_text)
        chunks = chunker.chunk_section(section, self.make_context(section.title))

        assert len(chunks) == 2

        assert (
            self.chunk_body(chunks[0])
            == "This is the first sentence. This is the second."
        )
        assert chunks[0].chunk_index == 0
        assert chunks[0].chunk_level == "sentence_group"

        assert self.chunk_body(chunks[1]) == "And the third."
        assert chunks[1].chunk_index == 1

    def test_overlap_tail_generation(self):
        input_text = "Sentence one. Sentence two. Sentence three. Sentence four."

        settings = Settings(
            chunk_size=6,
            chunk_overlap=3,
            chunk_context_size=50,
        )
        chunker = NaturalBoundaryChunker(settings)
        chunks = chunker.chunk_section(
            self.make_section(input_text), self.make_context()
        )

        assert len(chunks) == 2

        assert self.chunk_body(chunks[0]) == "Sentence one. Sentence two."
        assert (
            self.chunk_body(chunks[1])
            == "Sentence two. Sentence three. Sentence four."
        )

    def test_context_text_is_not_built_during_ingestion_chunking(self):
        input_text = "A. B. C. D. E."

        settings = Settings(
            chunk_size=1,
            chunk_overlap=0,
            chunk_context_size=15,
        )
        chunker = NaturalBoundaryChunker(settings)
        chunks = chunker.chunk_section(
            self.make_section(input_text), self.make_context()
        )

        assert len(chunks) == 5

        assert self.chunk_body(chunks[2]) == "C."
        assert chunks[2].context_text is None
        assert chunks[0].context_text is None

    def test_word_window_fallback(self):
        input_text = "This is a massive run on sentence that never ends and just keeps going and going."

        settings = Settings(
            chunk_size=10,
            chunk_overlap=0,
            chunk_context_size=50,
        )
        chunker = NaturalBoundaryChunker(settings)
        chunks = chunker.chunk_section(
            self.make_section(input_text), self.make_context()
        )

        assert len(chunks) > 1
        assert chunks[0].chunk_level == "word_window"
        assert (
            self.chunk_body(chunks[0])
            == "This is a massive run on sentence that never ends"
        )
        assert self.chunk_body(chunks[1]) == "and just keeps going and going."

    def test_cleaning_and_whitespace_normalization(self):
        input_text = (
            "Here is a bro-\nken word. \f  Lots of spaces.   \n\n\n\nToo many newlines."
        )

        settings = Settings(chunk_size=50, chunk_overlap=0, chunk_context_size=100)
        chunker = NaturalBoundaryChunker(settings)

        cleaned = chunker._clean(input_text)

        assert "broken word" in cleaned
        assert "\f" not in cleaned
        assert "Lots of spaces." in cleaned
        assert "\n\n\n" not in cleaned
        assert "\n\n" in cleaned

    def test_empty_or_whitespace_input(self):
        settings = Settings(chunk_size=10, chunk_overlap=0, chunk_context_size=10)
        chunker = NaturalBoundaryChunker(settings)

        assert (
            chunker.chunk_section(self.make_section(""), self.make_context()) == []
        )
        assert (
            chunker.chunk_section(self.make_section("   \n  \t  "), self.make_context())
            == []
        )

    def test_missing_book_id_requires_explicit_context(self):
        settings = Settings(chunk_size=10, chunk_overlap=0, chunk_context_size=10)
        chunker = NaturalBoundaryChunker(settings)
        section = Section(
            id=self.section_id,
            raw_text="A valid sentence.",
            extraction_status="NONE",
        )

        with pytest.raises(ValueError, match="book_id"):
            chunker.chunk_section(section)


def test_chunker_produces_output():
    settings = get_settings()
    chunker = NaturalBoundaryChunker(settings)

    sample_text = (
        "This is a test sentence about distributed systems. " * 60
    )

    section = Section(
        id="test-section-id",
        book_id="test-book-id",
        title="Test Section",
        raw_text=sample_text,
        extraction_status="NONE",
    )
    context = ChunkContext(
        book_id="test-book-id",
        book_title="Test Book",
        chapter_title="Chapter 1",
        section_title="Test Section",
    )
    chunks = chunker.chunk_section(section, context)

    print(f"\nchunk_size setting:    {settings.chunk_size}")
    print(f"chunk_overlap setting: {settings.chunk_overlap}")
    print(f"Chunks produced:       {len(chunks)}")
    if chunks:
        print(f"First chunk text_len:  {len(chunks[0].text)}")

    assert len(chunks) > 0, (
        f"Chunker returned empty list for {len(sample_text)}-char input. "
        f"chunk_size={settings.chunk_size}, overlap={settings.chunk_overlap}"
    )

import re
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from src.domain.config import Settings
from src.domain.section import Section
from src.domain.text_chunk import TextChunk
from src.domain.tokenizer import count_tokens

from src.ingestion._chunking._chunker import ChunkContext, Chunker


# TODO: Move text processing helpers into src/core/text_processor.py.
@dataclass
class _Sentence:
    text: str
    tokens: int


@dataclass
class _ChunkPiece:
    sentences: list[_Sentence]
    level: str


class NaturalBoundaryChunker(Chunker):
    """Split section text on natural boundaries while preserving context."""

    # Negative lookbehind for common abbreviations found in technical books.
    _ABBREV = (
        r"(?<!\bFig)(?<!\bfig)(?<!\bEq)(?<!\beq)"
        r"(?<!\be\.g)(?<!\bi\.e)(?<!\bvs)(?<!\bDr)"
        r"(?<!\bMr)(?<!\bMrs)(?<!\bProf)(?<!\bapprox)"
        r"(?<!\best)(?<!\bcf)(?<!\bNo)(?<!\bVol)(?<!\bpp)"
    )
    _SENT_SPLIT = re.compile(_ABBREV + r"(?<=[.!?])\s+")

    _HYPHEN_FIX = re.compile(r"-\s*\n\s*(\w)")
    _FORM_FEED = re.compile(r"\f")
    _HORIZ_WS = re.compile(r"[ \t]+")
    _MULTI_BLANK = re.compile(r"\n{3,}")

    def __init__(self, settings: Settings, **kwargs: Any) -> None:
        self._max_tokens = settings.chunk_size
        self._overlap_budget = settings.chunk_overlap

    def chunk_section(
        self, section: Section, context: ChunkContext | None = None
    ) -> list[TextChunk]:
        raw_text = section.raw_text

        context = context or self._context_from_section(section)

        cleaned = self._clean(raw_text)
        if not cleaned:
            return []

        paragraphs = self._parse(cleaned)

        raw_chunks = self._accumulate(paragraphs)
        if not raw_chunks:
            return []

        chunks: list[TextChunk] = []
        current_char_offset = 0

        for i, piece in enumerate(raw_chunks):
            body_text = self._join(piece.sentences)

            overlap_text = ""
            if i > 0 and self._overlap_budget:
                overlap_text = self._build_overlap_tail(raw_chunks[i - 1].sentences)

            full_chunk_text = (
                f"{overlap_text} {body_text}" if overlap_text else body_text
            )

            header = " > ".join(
                part
                for part in (
                    context.book_title,
                    context.chapter_title,
                    context.section_title,
                )
                if part
            )
            if header:
                full_chunk_text = f"[{header}]\n{full_chunk_text}"

            start_idx = current_char_offset
            end_idx = start_idx + len(body_text)

            chunks.append(
                TextChunk(
                    id=str(uuid4()),
                    book_id=context.book_id,
                    section_id=section.id,
                    text=full_chunk_text,
                    start_char=start_idx,
                    end_char=end_idx,
                    chunk_index=i,
                    chunk_level=piece.level,
                    word_count=len(body_text.split()),
                    context_text=None,
                )
            )

            current_char_offset = end_idx + 1

        return chunks

    @staticmethod
    def _context_from_section(section: Section) -> ChunkContext:
        book_id = getattr(section, "book_id", None)
        if not book_id:
            raise ValueError("section is missing book_id; pass an explicit ChunkContext")

        section_title = getattr(section, "title", "") or ""
        return ChunkContext(book_id=book_id, section_title=section_title)

    # TODO: Move to TextProcessor._clean().
    def _clean(self, text: str) -> str:
        text = self._FORM_FEED.sub("\n", text)
        text = self._HYPHEN_FIX.sub(r"\1", text)
        text = self._HORIZ_WS.sub(" ", text)
        return self._MULTI_BLANK.sub("\n\n", text).strip()

    # TODO: Move to TextProcessor._parse_sentences().
    def _parse(self, text: str) -> list[list[_Sentence]]:
        paragraphs: list[list[_Sentence]] = []
        for para_text in re.split(r"\n\n+", text):
            para_text = para_text.strip()
            if not para_text:
                continue

            raw_sentences = self._SENT_SPLIT.split(para_text)
            sentences = [
                _Sentence(text=s.strip(), tokens=self._tokens(s))
                for s in raw_sentences
                if s.strip()
            ]
            if sentences:
                paragraphs.append(sentences)
        return paragraphs

    # TODO: Move to TextProcessor._accumulate_chunks().
    def _accumulate(self, paragraphs: list[list[_Sentence]]) -> list[_ChunkPiece]:
        """Accumulate sentences into token-bounded chunks."""
        chunks: list[_ChunkPiece] = []
        current: list[_Sentence] = []
        current_t: int = 0

        for para in paragraphs:
            para_tokens = sum(s.tokens for s in para)

            if current and current_t + para_tokens > self._max_tokens:
                chunks.append(_ChunkPiece(current, "sentence_group"))
                current, current_t = [], 0

            for sent in para:
                if sent.tokens > self._max_tokens:
                    if current:
                        chunks.append(_ChunkPiece(current, "sentence_group"))
                        current, current_t = [], 0
                    for ws in self._word_window_split(sent.text):
                        chunks.append(_ChunkPiece([ws], "word_window"))
                    continue

                if current_t + sent.tokens > self._max_tokens and current:
                    chunks.append(_ChunkPiece(current, "sentence_group"))
                    current, current_t = [], 0

                current.append(sent)
                current_t += sent.tokens

        if current:
            chunks.append(_ChunkPiece(current, "sentence_group"))
        return chunks

    def _build_overlap_tail(self, prev_chunk: list[_Sentence]) -> str:
        """Return the last N sentences of prev_chunk that fit in the overlap budget."""
        tail: list[_Sentence] = []
        budget: int = self._overlap_budget
        for sent in reversed(prev_chunk):
            if sent.tokens > budget:
                break
            tail.append(sent)
            budget -= sent.tokens
        tail.reverse()
        return self._join(tail)

    # TODO: Move to TextProcessor._window_split().
    def _word_window_split(self, text: str) -> list[_Sentence]:
        """Split an oversized sentence into word-window sub-chunks."""
        words = text.split()
        step = self._max_tokens
        return [
            _Sentence(
                text=" ".join(words[i : i + step]),
                tokens=self._tokens(" ".join(words[i : i + step])),
            )
            for i in range(0, len(words), step)
        ]

    @classmethod
    def _tokens(cls, text: str) -> int:
        return count_tokens(text)

    # TODO: Move to TextProcessor.join_sentences().
    @staticmethod
    def _join(sentences: list[_Sentence]) -> str:
        return " ".join(s.text for s in sentences)

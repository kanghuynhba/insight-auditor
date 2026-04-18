import re
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import tiktoken
from src.core.config import Settings

from .chunker import Chunker
from .text_chunk import TextChunk


@dataclass
class _Sentence:
    text: str
    tokens: int


class NaturalBoundaryChunker(Chunker):
    """Chunker that splits text based on paragraphs and sentences, avoiding mid-sentence cuts.

    Improvements over the original:
    1. Accurate token counting via tiktoken (cl100k_base).
    2. Section title is prepended to every chunk so the model always has context.
    3. Paragraph-boundary-aware accumulation: a new paragraph prefers to start a
       new chunk rather than being appended mid-paragraph to the previous one.
    4. Abbreviation-aware sentence splitter that does not split on "Fig.", "e.g.",
       "i.e.", "vs.", "Dr.", etc.
    """

    # Negative lookbehind for common abbreviations found in technical books.
    _ABBREV = (
        r"(?<!\bFig)(?<!\bfig)(?<!\bEq)(?<!\beq)"
        r"(?<!\be\.g)(?<!\bi\.e)(?<!\bvs)(?<!\bDr)"
        r"(?<!\bMr)(?<!\bMrs)(?<!\bProf)(?<!\bapprox)"
        r"(?<!\best)(?<!\bcf)(?<!\bNo)(?<!\bVol)(?<!\bpp)"
    )
    _SENT_SPLIT = re.compile(_ABBREV + r"(?<=[.!?])\s+")

    # Text-cleaning patterns
    _HYPHEN_FIX = re.compile(r"-\s*\n\s*(\w)")
    _FORM_FEED = re.compile(r"\f")
    _HORIZ_WS = re.compile(r"[ \t]+")
    _MULTI_BLANK = re.compile(r"\n{3,}")

    # Shared tiktoken encoder (loaded once at class level)
    _ENCODER = tiktoken.get_encoding("cl100k_base")

    def __init__(self, settings: Settings, **kwargs: Any) -> None:
        self._max_tokens = settings.chunk_size
        self._overlap_budget = settings.chunk_overlap
        self._context_budget = settings.chunk_context_size

    # Public API
    def chunk_section(
        self,
        section_id: str,
        book_id: str,
        path_id: str,
        text: str,
        section_title: str = "",
    ) -> list[TextChunk]:
        """Chunk the text into natural-boundary chunks with expanded context.

        Args:
            section_id:     Identifier for the section being chunked.
            book_id:        Identifier for the parent book.
            path_id:        Identifier for the file path / TOC node.
            text:           Raw section text to chunk.
            section_title:  Human-readable title prepended to every chunk so
                            the LLM always knows which section it is reading.
        """
        cleaned = self._clean(text)
        if not cleaned:
            return []

        paragraphs = self._parse(cleaned)
        raw_chunks = self._accumulate(paragraphs)
        if not raw_chunks:
            return []

        overlapped = self._build_overlapped_texts(raw_chunks)
        context_windows = self._build_context_windows(overlapped)
        chunks: list[TextChunk] = []
        current_char_offset = 0

        for i, sentence_list in enumerate(raw_chunks):
            body_text = self._join(sentence_list)

            # overlap from previous chunk
            overlap_text = ""
            if i > 0 and self._overlap_budget:
                overlap_text = self._build_overlap_tail(raw_chunks[i - 1])

            full_chunk_text = (
                f"{overlap_text} {body_text}" if overlap_text else body_text
            )

            if section_title:
                full_chunk_text = f"[{section_title}]\n{full_chunk_text}"

            start_idx = current_char_offset
            end_idx = start_idx + len(body_text)

            chunks.append(
                TextChunk(
                    id=str(uuid4()),
                    book_id=book_id,
                    section_id=section_id,
                    path_id=path_id,
                    text=full_chunk_text,
                    start_char=start_idx,
                    end_char=end_idx,
                    chunk_index=i,
                    chunk_level=self._detect_level(overlapped[i]),
                    word_count=len(overlapped[i].split()),
                    context_text=context_windows[i],
                )
            )
            current_char_offset = end_idx + 1

        return chunks

    # Text cleaning
    def _clean(self, text: str) -> str:
        text = self._FORM_FEED.sub("\n", text)
        text = self._HYPHEN_FIX.sub(r"\1", text)
        text = self._HORIZ_WS.sub(" ", text)
        return self._MULTI_BLANK.sub("\n\n", text).strip()

    # Parsing: text → list[paragraph], each paragraph = list[_Sentence]
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

    # Accumulation: paragraphs → chunks (list[list[_Sentence]])
    def _accumulate(self, paragraphs: list[list[_Sentence]]) -> list[list[_Sentence]]:
        """Accumulate sentences into token-bounded chunks.

        When a new paragraph would push the current chunk over the token limit,
        we flush *before* adding the paragraph rather than splitting it mid-way.
        This keeps paragraphs together and respects semantic boundaries.
        Intra-paragraph splitting still happens when a single paragraph is larger
        than the token budget.
        """
        chunks: list[list[_Sentence]] = []
        current: list[_Sentence] = []
        current_t: int = 0

        for para in paragraphs:
            para_tokens = sum(s.tokens for s in para)

            # Flush before this paragraph if it would overflow and we have content.
            if current and current_t + para_tokens > self._max_tokens:
                chunks.append(current)
                current, current_t = [], 0

            for sent in para:
                # Handle a single sentence longer than the max budget.
                if sent.tokens > self._max_tokens:
                    if current:
                        chunks.append(current)
                        current, current_t = [], 0
                    for ws in self._word_window_split(sent.text):
                        chunks.append([ws])
                    continue

                # Intra-paragraph split: single sentence fills the budget.
                if current_t + sent.tokens > self._max_tokens and current:
                    chunks.append(current)
                    current, current_t = [], 0

                current.append(sent)
                current_t += sent.tokens

        if current:
            chunks.append(current)
        return chunks

    # Overlap construction
    def _build_overlapped_texts(self, raw_chunks: list[list[_Sentence]]) -> list[str]:
        texts: list[str] = []
        for i, chunk in enumerate(raw_chunks):
            body = self._join(chunk)
            if i == 0 or not self._overlap_budget:
                texts.append(body)
                continue
            tail = self._build_overlap_tail(raw_chunks[i - 1])
            texts.append(f"{tail} {body}" if tail else body)
        return texts

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

    # Context-window expansion
    def _build_context_windows(self, texts: list[str]) -> list[str]:
        windows: list[str] = []
        for i, core in enumerate(texts):
            budget = self._context_budget - self._tokens(core)
            parts = [core]
            lo, hi = i - 1, i + 1
            expanded = True

            while budget > 0 and expanded:
                expanded = False
                if lo >= 0 and self._tokens(texts[lo]) <= budget:
                    parts.insert(0, texts[lo])
                    budget -= self._tokens(texts[lo])
                    lo -= 1
                    expanded = True
                if hi < len(texts) and self._tokens(texts[hi]) <= budget:
                    parts.append(texts[hi])
                    budget -= self._tokens(texts[hi])
                    hi += 1
                    expanded = True

            windows.append(" ".join(parts))
        return windows

    # Helpers
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
        """
        This replaces the previous `len(text.split()) * 1.3` heuristic, which
        could be off by 20-30% for technical text with long compound words or
        code snippets.
        """
        return max(1, len(cls._ENCODER.encode(text)))

    @staticmethod
    def _join(sentences: list[_Sentence]) -> str:
        return " ".join(s.text for s in sentences)

    @staticmethod
    def _detect_level(text: str) -> str:
        if "\n\n" in text:
            return "paragraph"
        if re.search(r"[.!?]\s", text):
            return "sentence"
        return "word_window"

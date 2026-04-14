import re
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from src.core.config import Settings

from .chunker import Chunker
from .text_chunk import TextChunk


@dataclass
class _Sentence:
    text: str
    tokens: int


class NaturalBoundaryChunker(Chunker):
    """Chunker that splits text based on paragraphs and sentences, avoiding mid-sentence cuts."""

    _SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")
    _HYPHEN_FIX = re.compile(r"-\s*\n\s*(\w)")
    _FORM_FEED = re.compile(r"\f")
    _HORIZ_WS = re.compile(r"[ \t]+")
    _MULTI_BLANK = re.compile(r"\n{3,}")

    def __init__(self, settings: Settings, **kwargs: Any) -> None:
        self._max_tokens = settings.chunk_size
        self._overlap_budget = settings.chunk_overlap
        self._context_budget = settings.chunk_context_size

    def chunk_section(
        self,
        section_id: str,
        book_id: str,
        path_id: str,
        text: str,
    ) -> list[TextChunk]:
        """Chunk the text into natural boundary chunks with expanded context."""

        cleaned = self._clean(text)
        if not cleaned:
            return []

        paragraphs = self._parse(cleaned)
        raw_chunks = self._accumulate(paragraphs)
        if not raw_chunks:
            return []

        overlapped = self._build_overlapped_texts(raw_chunks)
        context_windows = self._build_context_windows(overlapped)

        current_start = 0
        chunks = []

        for i, chunk_text in enumerate(overlapped):
            start_idx = text.find(chunk_text, current_start)
            if start_idx == -1:
                start_idx = current_start
            end_idx = start_idx + len(chunk_text)
            current_start = end_idx
            chunks.append(
                TextChunk(
                    id=str(uuid4()),
                    book_id=book_id,
                    section_id=section_id,
                    path_id=path_id,
                    text=overlapped[i],
                    start_char=start_idx,
                    end_char=end_idx,
                    context_text=context_windows[i],
                    chunk_index=i,
                    chunk_level=self._detect_level(overlapped[i]),
                    word_count=len(overlapped[i].split()),
                )
            )

        return chunks

    def _clean(self, text: str) -> str:
        text = self._FORM_FEED.sub("\n", text)
        text = self._HYPHEN_FIX.sub(r"\1", text)
        text = self._HORIZ_WS.sub(" ", text)
        return self._MULTI_BLANK.sub("\n\n", text).strip()

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

    def _accumulate(self, paragraphs: list[list[_Sentence]]) -> list[list[_Sentence]]:
        chunks: list[list[_Sentence]] = []
        current: list[_Sentence] = []
        current_t: int = 0

        for para in paragraphs:
            for sent in para:
                if sent.tokens > self._max_tokens:
                    if current:
                        chunks.append(current)
                        current, current_t = [], 0
                    for ws in self._word_window_split(sent.text):
                        chunks.append([ws])
                    continue

                if current_t + sent.tokens > self._max_tokens and current:
                    chunks.append(current)
                    current, current_t = [], 0

                current.append(sent)
                current_t += sent.tokens

        if current:
            chunks.append(current)
        return chunks

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
        tail: list[_Sentence] = []
        budget: int = self._overlap_budget
        for sent in reversed(prev_chunk):
            if sent.tokens > budget:
                break
            tail.append(sent)
            budget -= sent.tokens
        tail.reverse()
        return self._join(tail)

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

    def _word_window_split(self, text: str) -> list[_Sentence]:
        words = text.split()
        step = self._max_tokens
        return [
            _Sentence(
                text=" ".join(words[i : i + step]),
                tokens=self._tokens(" ".join(words[i : i + step])),
            )
            for i in range(0, len(words), step)
        ]

    @staticmethod
    def _tokens(text: str) -> int:
        return max(1, int(len(text.split()) * 1.3))

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

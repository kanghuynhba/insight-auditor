# src/infrastructure/loaders/pdf_loader.py
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import fitz
from src.core.config import Settings
from src.core.models import Book, Chapter, Section

from .file_type import FileType
from .loader import Loader


# TODO: Move to src/infrastructure/loaders/_raw_entry.py - internal dataclass for PDF parsing
@dataclass
class _RawEntry:
    """Internal data structure to hold extraction results before domain mapping."""

    title: str
    raw_text: str
    index: int
    level: int


# TODO: Move to src/infrastructure/loaders/path_counter.py - path ID generation is reusable
@dataclass
class _PathCounter:
    """
    Generates path ids (e.g. '001', '001.002')
    """

    def __init__(self) -> None:
        self._counters: Dict[int, int] = {}

    def next(self, level: int) -> str:
        """Generates a breadcrumb string like '001.002.004'."""

        self._counters[level] = self._counters.get(level, 0) + 1

        levels_to_reset = [l for l in self._counters if l > level]

        for l in levels_to_reset:
            del self._counters[l]

        # Build path string: 001.002...
        parts = [f"{self._counters.get(i, 0):03d}" for i in range(1, level + 1)]
        return ".".join(parts)


class PdfLoader(Loader):
    def __init__(self, settings: Settings):
        self._settings = settings

    def load(self, path: Path) -> Book:
        with fitz.open(str(path)) as doc:
            title = self._detect_title(doc, path)
            raw_entries = self._extract_entries(doc)

        book_id = self._generate_toc_hash(title, raw_entries)
        chapters = self._build_chapters(raw_entries, book_id)

        # Instantiate the frozen Book model
        book = Book(
            id=book_id,
            title=title,
            source_format=FileType.Pdf,
            file_path=str(path),
            source_filename=path.name,
            total_chapters=len(chapters),
            chapters=chapters,
        )
        return book

    def _generate_toc_hash(self, title: str, entries: List[_RawEntry]) -> str:
        """
        Creates a deterministic SHA-256 fingerprint of the book's structure.
        Similar to gen_sha512_hash in GraphRAG[cite: 20].
        """
        # Create a string representation of the TOC: Title + Levels + Entry Titles
        # We include levels and indices to catch structural changes even if titles are same
        fingerprint_parts = [title]
        for entry in entries:
            fingerprint_parts.append(f"{entry.level}:{entry.title}")

        fingerprint_str = "|".join(fingerprint_parts)

        return hashlib.sha256(fingerprint_str.encode()).hexdigest()

    # TODO: Refactor into separate toc_extractor.py - TOC vs heuristic extraction
    def _extract_entries(self, doc: fitz.Document) -> List[_RawEntry]:
        """
        Orchestrates chapter extraction. Tries TOC first, falls back to heuristics.
        """
        toc = doc.get_toc()

        if toc:
            return self._extract_via_toc(doc, toc)

        return self._extract_via_heuristic(doc)

    # TODO: Move to toc_extractor.py - TOC-based extraction logic
    def _extract_via_toc(self, doc: fitz.Document, toc: list) -> List[_RawEntry]:
        """Extracts chapters cleanly using the PDF's internal Table of Contents."""
        entries: list[_RawEntry] = []

        for i in range(len(toc)):
            level, title, start_page = toc[i]

            end_page = toc[i + 1][2] if i + 1 < len(toc) else doc.page_count
            start_index = max(0, start_page - 1)
            end_index = max(0, end_page - 1)

            text = self._extract_page_range(doc, start_index, end_index)

            if not text:
                continue

            entries.append(_RawEntry(title=title, raw_text=text, index=i, level=level))

        return entries

    # TODO: Move to toc_extractor.py - font-size based fallback extraction
    def _extract_via_heuristic(self, doc: fitz.Document) -> List[_RawEntry]:
        """
        Treats large font spans as headings.  Font-size thresholds:
            >= 20 pt  → level 1 (chapter)
            16–19 pt  → level 2 (section)
            13–15 pt  → level 3 (subsection)
        Everything else is body text that belongs to the current heading.
        """
        entries: list[_RawEntry] = []
        pending_title = "Introduction"
        pending_level = 1
        pending_text: list[str] = []
        index = 0

        def _flush() -> None:
            nonlocal index
            body = " ".join(pending_text).strip()
            if body:
                entries.append(
                    _RawEntry(
                        title=pending_title,
                        raw_text=body,
                        level=pending_level,
                        index=index,
                    )
                )
                index += 1

        for page in doc:
            for block in page.get_text("dict").get("blocks", []):
                if block.get("type") != 0:  # 0 = text block
                    continue
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = span["text"].strip()
                        if not text:
                            continue

                        level = self._heading_level(span["size"])

                        if level and 2 < len(text) < 100:
                            _flush()
                            pending_title = text
                            pending_level = level
                            pending_text = []
                        else:
                            pending_text.append(text)

            pending_text.append("\n")  # preserve page breaks in body

        _flush()
        return entries

    # TODO: Move to book_builder.py - section/chapter building logic
    def _build_chapters(self, entries: list[_RawEntry], book_id: str) -> list[Chapter]:
        """
        Level-1 entries become Chapters.
        Level-2+ entries become Sections inside the most-recent Chapter.

        Entries deeper than settings.deepest_level are silently skipped.
        """
        chapters: list[Chapter] = []
        active_chapter: Optional[Chapter] = None
        counter = _PathCounter()

        for entry in entries:
            if entry.level > self._settings.deepest_level:
                continue

            path_id = counter.next(entry.level)

            if entry.level == 1:
                active_chapter = Chapter(
                    book_id=book_id,
                    title=entry.title,
                    path_id=path_id,
                    index=entry.index,
                    sections=[],
                )
                chapters.append(active_chapter)
            else:
                if active_chapter is None:
                    synthetic_path = counter.next(1)
                    active_chapter = Chapter(
                        book_id=book_id,
                        title="Preface",
                        path_id=synthetic_path,
                        index=0,
                    )
                    chapters.append(active_chapter)

                parent_path = ".".join(path_id.split(".")[:-1])

                section = Section(
                    chapter_id=active_chapter.id,
                    path_id=path_id,
                    title=entry.title,
                    parent_path_id=parent_path,
                    level=entry.level,
                    raw_text=entry.raw_text,
                    atomic_facts=[],
                )
                active_chapter.sections.append(section)

        return chapters

    # TODO: Move to book_builder.py - page-to-text extraction
    def _extract_page_range(self, doc: fitz.Document, first: int, last: int) -> str:
        parts = []
        for page_num in range(first, min(last, doc.page_count)):
            parts.append(doc[page_num].get_text("text"))
        return "\n\n".join(parts).strip()

    # TODO: Move to book_builder.py - font size to heading level mapping
    @staticmethod
    def _heading_level(font_size: float) -> Optional[int]:
        """Returns 1, 2, or 3 for heading sizes; None for body text."""

        if font_size >= 20:
            return 1

        if font_size >= 16:
            return 2

        if font_size >= 13:
            return 3

        return None

    # TODO: Move to book_builder.py - title detection from metadata or filename
    @staticmethod
    def _detect_title(doc: fitz.Document, file_path: Path) -> str:
        """
        Checks metadata first, then falls back to a beautifully formatted filename.
        """
        #  Grab the embedded metadata
        metadata_title = doc.metadata.get("title", "").strip()

        # Check if the metadata is a generic system default
        garbage_phrases = ["microsoft word", "untitled", "document", "scan", "copy"]
        is_garbage = any(phrase in metadata_title.lower() for phrase in garbage_phrases)

        # If the metadata is good, we are done!
        if metadata_title and not is_garbage:
            return metadata_title

        # Fallback: Turn "atomic_habits-v2.pdf" into "Atomic Habits V2"
        clean_filename = file_path.stem.replace("_", " ").replace("-", " ").title()

        return clean_filename

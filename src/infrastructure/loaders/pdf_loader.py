# src/infrastructure/loaders/pdf_loader.py

import fitz
from pathlib import Path
from dataclasses import dataclass
from typing import List, Tuple

from src.core.config import Settings
from src.core.book import Book
from src.core.chapter import Chapter
from src.core.enums import FileFormat

@dataclass
class RawChapter:
    """Internal data structure to hold extraction results before domain mapping."""
    title: str
    raw_text: str
    index: int
    level: int

class PdfLoader:
    def __init__(self, settings: Settings):
        self._settings=settings

    def load(self, path: Path) -> Tuple[Book, List[Chapter]]:
        with fitz.open(str(path)) as doc:
            title=self._detect_title(doc, path)
            raw_chapters=self._extract_chapters(doc)

        # Instantiate the frozen Book model
        book= Book(
            title=title,
            source_format=FileFormat.PDF,
            source_filename=path.name,
            total_chapters=len(raw_chapters)
        )

        chapters=[]
        active_parents: list[str | None] = [None] * (self._settings.DEEPEST_LEVEL + 1)

        for raw in raw_chapters:
            safe_level = min(raw.level, self._settings.DEEPEST_LEVEL)

            parent_id = active_parents[raw.level-1] if safe_level > 1 else None

            new_chapter = Chapter(
                book_id=book.id,
                title=raw.title,
                index=raw.index,
                raw_text=raw.raw_text,
                level=safe_level,
                parent_id=parent_id
            )

            active_parents[safe_level] = new_chapter.id

            # If we move from 2.1.5 back to 2.2, everything at level 3+ is reset
            for i in range(safe_level + 1, len(active_parents)):
                active_parents[i] = None

            chapters.append(new_chapter)

        return book, chapters

    def _detect_title(self, doc: fitz.Document, file_path: Path) -> str:
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

    def _extract_chapters(self, doc: fitz.Document) -> List[RawChapter]:
        """
        Orchestrates chapter extraction. Tries TOC first, falls back to heuristics.
        """
        toc = doc.get_toc()

        if toc:
            return self._extract_via_toc(doc, toc)

        return self._extract_via_heuristic(doc)

    def _extract_via_toc(self, doc: fitz.Document, toc: list) -> List[RawChapter]:
        """Extracts chapters cleanly using the PDF's internal Table of Contents."""
        raw_chapters = []

        for i in range(len(toc)):
            level, title, start_page = toc[i]

            end_page = toc[i+1][2] if i + 1 < len(toc) else doc.page_count
            start_index = max(0, start_page - 1)
            end_index = max(0, end_page - 1)

            chapter_text = ""
            for page_num in range(start_index, end_index):
                if page_num < doc.page_count:
                    chapter_text += doc[page_num].get_text("text") + "\n\n"

            if chapter_text.strip():
                raw_chapters.append(
                    RawChapter(
                        title=title,
                        raw_text=chapter_text.strip(),
                        index=i,
                        level=level
                    )
                )

        return raw_chapters
    def _extract_via_heuristic(self, doc: fitz.Document) -> List[RawChapter]:
        raw_chapters = []
        current_text = ""
        current_title = "Introduction"
        current_level = 1
        global_index = 0

        for page_num in range(doc.page_count):
            blocks = doc[page_num].get_text("dict").get("blocks", [])
            for block in blocks:
                if block.get("type") != 0: continue

                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = span["text"].strip()
                        size = span["size"]

                        # Refined Thresholds
                        level = 0
                        if size >= 20: level = 1       # Main Chapter
                        elif 16 <= size < 20: level = 2 # Section
                        elif 13 <= size < 16: level = 3 # Sub-section                        

                        if level > 0 and 2 < len(text) < 100:
                            if current_text.strip():
                                raw_chapters.append(RawChapter(
                                    title=current_title,
                                    raw_text=current_text.strip(),
                                    index=global_index,
                                    level=current_level
                                ))
                                global_index += 1
                                current_text = ""

                            current_title = text
                            current_level = level
                        else:
                            current_text += text + " "
            current_text += "\n"

        # Final append
        if current_text.strip():
            raw_chapters.append(RawChapter(
                title=current_title,
                raw_text=current_text.strip(),
                index=global_index,
                level=current_level
            ))

        return raw_chapters

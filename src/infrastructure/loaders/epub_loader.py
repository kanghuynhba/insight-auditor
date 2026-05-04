# src/infrastructure/loaders/epub_loader.py
import hashlib
import logging
from pathlib import Path
from typing import Optional, Dict
from uuid import uuid4

from ebooklib import epub

from src.core.book import Book
from src.core.config import Settings
from src.core.section import Section
from src.core.toc_node import TocNode
from src.infrastructure.loaders.file_type import FileType
from src.infrastructure.loaders.loader import Loader
from src.infrastructure.loaders.toc_builders.epub_toc_builder import (
    EpubTocBuilder,
)
from src.infrastructure.loaders.text_extractors.epub_text_extractor import (
    EpubTextExtractor,
)
from src.services.toc_service import TOCService

logger = logging.getLogger(__name__)


class EpubLoader(Loader):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def load(self, path: Path) -> Book:
        logger.info("EpubLoader: loading %s", path)
        epub_book = epub.read_epub(str(path), {"ignore_ncx": False})

        title = self._extract_title(epub_book)
        author = self._extract_author(epub_book)

        # Get fake root TocNode containing all TOC nodes as children
        toc_root = EpubTocBuilder.build(epub_book)
        book_id = self._compute_stable_id(title, toc_root)
        content_map = EpubTextExtractor.extract_texts(epub_book, toc_root)

        # Attach sections to TocNode
        self._attach_sections(toc_root, content_map)

        # Create Book
        book = Book(
            id=book_id,
            title=title,
            author=author,
            source_format=FileType.Epub,
            file_path=str(path),
            source_filename=path.name,
        )

        # Convert TocNode tree to DB entities
        book.table_of_contents = TOCService.to_entities(toc_root, book.id)

        return book

    # ------------------------------------------------------------------
    # Stable book ID computation
    # ------------------------------------------------------------------
    def _compute_stable_id(self, title: str, toc_root: TocNode) -> str:
        parts = [title]

        def collect(node: TocNode, depth: int) -> None:
            for child in node.children:
                parts.append(f"{depth}:{child.title}")
                collect(child, depth + 1)

        collect(toc_root, 1)
        return hashlib.sha256("|".join(parts).encode()).hexdigest()

    # ------------------------------------------------------------------
    # Attach sections to TocNode
    # ------------------------------------------------------------------
    def _attach_sections(self, node: TocNode, content_map: Dict[str, str]) -> None:
        """
        Recursively attach Section objects to TocNode based on href.
        """
        # Skip fake root (level 0)
        if node.level > 0 and node.href:
            raw_text = content_map.get(node.href, "")
            section = Section(
                raw_text=raw_text if raw_text else "",
                extraction_status="NONE",
            )
            node.section = section
            node.section_id = section.id

        # Recursively process children
        for child in node.children:
            self._attach_sections(child, content_map)

    # ------------------------------------------------------------------
    # Metadata helpers
    # ------------------------------------------------------------------
    def _extract_title(self, epub_book: epub.EpubBook) -> str:
        titles = epub_book.get_metadata("DC", "title")
        return titles[0][0].strip() if titles else "Unknown Title"

    def _extract_author(self, epub_book: epub.EpubBook) -> Optional[str]:
        creators = epub_book.get_metadata("DC", "creator")
        return creators[0][0].strip() if creators else None

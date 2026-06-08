# src/infrastructure/loaders/epub_loader.py
import shutil
import zipfile
import hashlib
import logging
from pathlib import Path
from typing import Optional, Dict

from ebooklib import epub

from src.domain.book import Book
from src.domain.config import Settings
from src.domain.section import Section
from src.domain.toc_node import TocNode
from src.ingestion._loaders._base import ExtractedBookData, Loader
from src.ingestion._loaders.toc_builders.epub_toc_builder import (
    EpubTocBuilder,
)
from src.ingestion._loaders.text_extractors.epub_text_extractor import (
    EpubTextExtractor,
)

logger = logging.getLogger(__name__)


class EpubLoader(Loader):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._current_path: Path | None = None
        self._cached_data: dict | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_stable_id(self, path: Path) -> str:
        data = self._ensure_loaded(path)
        return self._compute_stable_id(data["title"], data["toc_root"])

    def extract_raw(self, path: Path) -> ExtractedBookData:
        # This will either use the cache from get_stable_id or load it fresh
        data = self._ensure_loaded(path)

        logger.info("EpubLoader: extracting content for %s", path)

        content_map = EpubTextExtractor.extract_texts(
            data["epub_book"], data["toc_root"]
        )
        self._attach_sections(data["toc_root"], content_map)

        return ExtractedBookData(
            title=data["title"],
            author=data["author"],
            toc_root=data["toc_root"],
        )

    @staticmethod
    def extract_to_static(epub_path: Path, book_id: str, static_root: Path) -> Path:
        """Extract EPUB contents into static_root/book_id and return the path."""
        extract_dir = static_root / book_id
        if extract_dir.exists():
            shutil.rmtree(extract_dir)  # clean previous extraction
        extract_dir.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(epub_path, "r") as zip_ref:
            zip_ref.extractall(extract_dir)

        return extract_dir

    def _ensure_loaded(self, path: Path) -> dict:
        """Internal helper to parse only if necessary."""
        if self._current_path == path and self._cached_data:
            return self._cached_data

        epub_book = epub.read_epub(str(path), {"ignore_ncx": False})
        title = self._extract_title(epub_book)
        toc_root = EpubTocBuilder.build(epub_book)

        self._current_path = path
        self._cached_data = {
            "epub_book": epub_book,
            "title": title,
            "toc_root": toc_root,
            "author": self._extract_author(epub_book),
        }
        return self._cached_data

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

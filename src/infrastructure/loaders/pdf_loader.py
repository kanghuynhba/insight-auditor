# src/infrastructure/loaders/pdf_loader.py

import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import fitz

from src.core.book import Book
from src.core.config import Settings
from src.core.enums import ExtractionStatus
from src.core.helpers import new_id
from src.core.section import Section
from src.core.table_of_content import TableOfContent
from src.infrastructure.loaders.common.markdown_converter import (
    clean_markdown_text,
)
from src.infrastructure.loaders.common.path_counter import PathCounter
from src.infrastructure.loaders.file_type import FileType
from src.infrastructure.loaders.loader import Loader

logger = logging.getLogger(__name__)


@dataclass
class _TocNode:
    title: str
    level: int
    page: int  # 1‑based page number
    children: List["_TocNode"] = field(default_factory=list)

    def __hash__(self) -> int:
        return id(self)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, _TocNode):
            return False
        return self is other


class PdfLoader(Loader):
    def __init__(self, settings: Settings):
        self._settings = settings

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def load(self, path: Path) -> Book:
        logger.info("PdfLoader: loading %s", path)
        with fitz.open(str(path)) as doc:
            title = self._detect_title(doc, path)

            # 1. Build TOC tree
            toc_nodes = self.build_toc(doc)

            # 2. Compute stable book ID
            book_id = self.compute_stable_id(title, toc_nodes)

            book = Book(
                id=book_id,
                title=title,
                source_format=FileType.Pdf,
                file_path=str(path),
                source_filename=path.name,
            )

            # 3. Process book: create sections, extract text with page boundaries
            self.process_book(doc, toc_nodes, book_id, book)

            logger.info("PdfLoader: finished – %d TOC entries", len(book.toc))
            return book

    # ------------------------------------------------------------------
    # 1. Build Table of Contents
    # ------------------------------------------------------------------
    def build_toc(self, doc: fitz.Document) -> List[_TocNode]:
        """Build hierarchical TOC from PDF's built-in outline or heuristic."""
        toc = doc.get_toc()
        if toc:
            return self._build_tree_from_pdf_toc(toc)
        return self._build_tree_from_heuristic(doc)

    def _build_tree_from_pdf_toc(
        self, toc: List[Tuple[int, str, int]]
    ) -> List[_TocNode]:
        root: List[_TocNode] = []
        stack: List[_TocNode] = []

        for level, title, page in toc:
            node = _TocNode(title=title, level=level, page=page)
            while stack and stack[-1].level >= level:
                stack.pop()
            if stack:
                stack[-1].children.append(node)
            else:
                root.append(node)
            stack.append(node)
        return root

    def _build_tree_from_heuristic(self, doc: fitz.Document) -> List[_TocNode]:
        nodes: List[_TocNode] = []
        current_title = "Introduction"
        current_page = 1

        for page_num in range(doc.page_count):
            page = doc[page_num]
            blocks = page.get_text("dict").get("blocks", [])
            for block in blocks:
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = span["text"].strip()
                        if not text:
                            continue
                        level = self._heading_level(span["size"])
                        if level and 2 < len(text) < 100:
                            if current_title:
                                nodes.append(
                                    _TocNode(
                                        title=current_title, level=1, page=current_page
                                    )
                                )
                            current_title = text
                            current_page = page_num + 1
        if current_title:
            nodes.append(_TocNode(title=current_title, level=1, page=current_page))
        return nodes

    @staticmethod
    def _heading_level(font_size: float) -> Optional[int]:
        if font_size >= 20:
            return 1
        if font_size >= 16:
            return 2
        if font_size >= 13:
            return 3
        return None

    # ------------------------------------------------------------------
    # 2. Compute Stable Book ID (from title + TOC structure)
    # ------------------------------------------------------------------
    def compute_stable_id(self, title: str, toc_nodes: List[_TocNode]) -> str:
        parts = [title]

        def collect(node_list: List[_TocNode], depth: int) -> None:
            for n in node_list:
                parts.append(f"{depth}:{n.title}:{n.page}")
                collect(n.children, depth + 1)

        collect(toc_nodes, 1)
        return hashlib.sha256("|".join(parts).encode()).hexdigest()

    # ------------------------------------------------------------------
    # 3. Process Book – create sections and extract text with page boundaries
    # ------------------------------------------------------------------
    def process_book(
        self,
        doc: fitz.Document,
        toc_nodes: List[_TocNode],
        book_id: str,
        book: Book,
    ) -> None:
        # Flatten TOC tree
        flat_entries = self._flatten_toc(toc_nodes)

        # Create empty Section and TableOfContent objects
        node_to_toc, temp_toc = self._create_empty_sections(flat_entries, book_id)

        # Set parent_id for TOC hierarchy
        self._set_toc_parents(toc_nodes, node_to_toc)

        # Compute page boundaries (start_page, end_page) for each node
        boundaries = self._compute_page_boundaries(flat_entries, doc.page_count)

        # Extract raw_text for each node using boundaries
        self._extract_texts_from_boundaries(doc, boundaries, node_to_toc)

        # Attach to book
        book.toc = temp_toc

    # --- Helper methods for processing ---
    def _flatten_toc(self, nodes: List[_TocNode]) -> List[Tuple[_TocNode, int]]:
        result: List[Tuple[_TocNode, int]] = []

        def flatten(node: _TocNode, level: int) -> None:
            result.append((node, level))
            for child in node.children:
                flatten(child, level + 1)

        for node in nodes:
            flatten(node, 1)
        return result

    def _create_empty_sections(
        self, flat_entries: List[Tuple[_TocNode, int]], book_id: str
    ) -> Tuple[Dict[_TocNode, TableOfContent], List[TableOfContent]]:
        path_counter = PathCounter()
        node_to_toc: Dict[_TocNode, TableOfContent] = {}
        temp_toc: List[TableOfContent] = []
        order = 0

        for node, level in flat_entries:
            path_id = path_counter.next(level)
            parent_path_id = (
                ".".join(path_id.split(".")[:-1]) if "." in path_id else None
            )
            section = Section(
                id=new_id(),
                book_id=book_id,
                path_id=path_id,
                parent_path_id=parent_path_id,
                title=node.title,
                level=level,
                raw_text=None,
                extraction_status=ExtractionStatus.NONE,
            )
            toc_entry = TableOfContent(
                id=new_id(),
                book_id=book_id,
                section_id=section.id,
                parent_id=None,
                level=level,
                order=order,
                title=node.title,
                section=section,
            )
            order += 1
            node_to_toc[node] = toc_entry
            temp_toc.append(toc_entry)

        return node_to_toc, temp_toc

    def _set_toc_parents(
        self, root_nodes: List[_TocNode], node_to_toc: Dict[_TocNode, TableOfContent]
    ) -> None:
        def set_parents(node: _TocNode, parent_id: Optional[str]) -> None:
            entry = node_to_toc[node]
            entry.parent_id = parent_id
            for child in node.children:
                set_parents(child, entry.id)

        for node in root_nodes:
            set_parents(node, None)

    def _compute_page_boundaries(
        self,
        flat_entries: List[Tuple[_TocNode, int]],
        total_pages: int,
    ) -> Dict[_TocNode, Tuple[int, int]]:
        """Returns dict node -> (start_page, end_page), both 1‑based, end_page exclusive."""
        # Sort entries by page order (reading order)
        sorted_entries = sorted(flat_entries, key=lambda x: x[0].page)
        boundaries: Dict[_TocNode, Tuple[int, int]] = {}
        for i, (node, _) in enumerate(sorted_entries):
            start_page = node.page
            if i + 1 < len(sorted_entries):
                next_node = sorted_entries[i + 1][0]
                end_page = next_node.page  # exclusive: stop before next heading
            else:
                end_page = total_pages + 1
            boundaries[node] = (start_page, end_page)
        return boundaries

    def _extract_texts_from_boundaries(
        self,
        doc: fitz.Document,
        boundaries: Dict[_TocNode, Tuple[int, int]],
        node_to_toc: Dict[_TocNode, TableOfContent],
    ) -> None:
        for node, toc_entry in node_to_toc.items():
            bounds = boundaries.get(node)
            if not bounds:
                toc_entry.section.raw_text = ""
                continue
            start_page, end_page = bounds
            if start_page > end_page or start_page < 1:
                toc_entry.section.raw_text = ""
                continue
            # Convert to 0‑based indices for PyMuPDF
            text = self._extract_page_range(doc, start_page - 1, end_page - 1)
            toc_entry.section.raw_text = text or ""

    def _extract_page_range(self, doc: fitz.Document, first: int, last: int) -> str:
        """Extract pages from first (0‑based) to last (inclusive) as clean markdown."""
        parts = []
        for page_num in range(first, min(last, doc.page_count)):
            page = doc[page_num]
            text_dict = page.get_text("dict")
            page_md = ""
            # if text_dict and "blocks" in text_dict:
            #     # page_md = blocks_to_markdown(text_dict["blocks"])
            # else:
            #     # page_md = plain_to_markdown(page.get_text("text"))
            parts.append(page_md)
        combined = "\n\n".join(parts)
        return clean_markdown_text(combined)

    # ------------------------------------------------------------------
    # Metadata helpers (unchanged)
    # ------------------------------------------------------------------
    def _detect_title(self, doc: fitz.Document, file_path: Path) -> str:
        metadata_title = doc.metadata.get("title", "").strip()
        garbage_phrases = ["microsoft word", "untitled", "document", "scan", "copy"]
        is_garbage = any(phrase in metadata_title.lower() for phrase in garbage_phrases)
        if metadata_title and not is_garbage:
            return metadata_title
        return file_path.stem.replace("_", " ").replace("-", " ").title()

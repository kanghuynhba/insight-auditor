# src/infrastructure/loaders/text_extractors/pdf_text_extractor.py
"""Extract section text from PDF page ranges."""

import logging
from typing import Dict, List, Optional, Tuple

import fitz

from src.domain.toc_node import TocNode
from src.ingestion._loaders.common.markdown_converter import clean_markdown_text

logger = logging.getLogger(__name__)

_HEADING_PREFIXES: List[Tuple[float, str]] = [
    (20.0, "# "),
    (16.0, "## "),
    (13.0, "### "),
]


class PdfTextExtractor:
    @classmethod
    def extract_texts(cls, doc: fitz.Document, toc_root: TocNode) -> Dict[str, str]:
        """Extract text for each TOC section."""
        flat_nodes = cls._flatten_toc(toc_root)
        if not flat_nodes:
            return {}

        boundaries = cls._compute_page_boundaries(flat_nodes, doc.page_count)
        content_map: Dict[str, str] = {}

        for node in flat_nodes:
            if not node.href:
                continue
            bounds = boundaries.get(node.href)
            if bounds is None:
                continue

            start_page, end_page = bounds
            markdown = cls._extract_page_range(doc, start_page, end_page)
            if markdown.strip():
                content_map[node.href] = markdown
                logger.debug(
                    "PdfTextExtractor: extracted '%s' pages %d-%d (%d chars)",
                    node.title,
                    start_page,
                    end_page,
                    len(markdown),
                )

        return content_map

    # ------------------------------------------------------------------
    # Flat navigation (mirrors EpubTextExtractor._flatten_toc)
    # ------------------------------------------------------------------

    @classmethod
    def _flatten_toc(cls, node: TocNode) -> List[TocNode]:
        """Depth-first flattening, skipping the fake root (level 0).

        Mirrors ``EpubTextExtractor._flatten_toc()``.
        """
        result: List[TocNode] = []
        if node.level > 0:
            result.append(node)
        for child in node.children:
            result.extend(cls._flatten_toc(child))
        return result

    # ------------------------------------------------------------------
    # Page boundary computation (PDF analogue of stop-anchor logic)
    # ------------------------------------------------------------------

    @classmethod
    def _compute_page_boundaries(
        cls, flat_nodes: List[TocNode], total_pages: int
    ) -> Dict[str, Tuple[int, int]]:
        """Return href → (start_page, end_page), both 1-based, end exclusive.

        Nodes are sorted by their page number (their ``href``) so that
        overlapping TOC entries (e.g. a chapter heading that shares a page
        with the first sub-section) are handled in reading order.

        This is the PDF counterpart of ``EpubTextExtractor._find_stop_anchor()``:
        instead of scanning for the next sibling anchor in the HTML, we
        scan for the next entry in the sorted flat list.
        """
        # Sort by page number (href stores the 1-based page as a string)
        try:
            sorted_nodes = sorted(flat_nodes, key=lambda n: int(n.href or "0"))
        except ValueError:
            logger.warning("PdfTextExtractor: non-numeric href found, skipping sort")
            sorted_nodes = flat_nodes

        boundaries: Dict[str, Tuple[int, int]] = {}
        for i, node in enumerate(sorted_nodes):
            if not node.href:
                continue
            start_page = int(node.href)
            if i + 1 < len(sorted_nodes) and sorted_nodes[i + 1].href:
                end_page = int(sorted_nodes[i + 1].href)  # exclusive
            else:
                end_page = total_pages + 1

            boundaries[node.href] = (start_page, end_page)

        return boundaries

    # ------------------------------------------------------------------
    # Text extraction
    # ------------------------------------------------------------------

    @classmethod
    def _extract_page_range(
        cls, doc: fitz.Document, start_page: int, end_page: int
    ) -> str:
        """Extract pages [start_page, end_page) as clean Markdown.

        ``start_page`` and ``end_page`` are 1-based; ``end_page`` is
        exclusive (same convention as ``_compute_page_boundaries``).
        PyMuPDF pages are 0-based, so we subtract 1 on access.
        """
        parts: List[str] = []
        first = start_page - 1  # convert to 0-based
        last = min(end_page - 1, doc.page_count)  # exclusive, 0-based

        for page_idx in range(first, last):
            page = doc[page_idx]
            page_md = cls._page_to_markdown(page)
            if page_md:
                parts.append(page_md)

        combined = "\n\n".join(parts)
        return clean_markdown_text(combined)

    @classmethod
    def _page_to_markdown(cls, page: fitz.Page) -> str:
        """Convert a single PDF page to Markdown.

        Iterates the block → line → span tree produced by PyMuPDF and
        promotes heading-sized spans to Markdown headings.  Body text is
        collected into paragraphs separated by blank lines.
        """
        text_dict = page.get_text("dict")
        paragraphs: List[str] = []
        current_paragraph: List[str] = []

        for block in text_dict.get("blocks", []):
            if block.get("type") != 0:  # skip image blocks
                continue

            block_lines: List[str] = []
            for line in block.get("lines", []):
                line_parts: List[str] = []
                for span in line.get("spans", []):
                    text = span["text"].strip()
                    if not text:
                        continue
                    prefix = cls._heading_prefix(span["size"])
                    if prefix:
                        # Flush pending paragraph before emitting heading
                        if current_paragraph:
                            paragraphs.append(" ".join(current_paragraph))
                            current_paragraph = []
                        paragraphs.append(f"{prefix}{text}")
                    else:
                        line_parts.append(text)

                if line_parts:
                    block_lines.append(" ".join(line_parts))

            if block_lines:
                current_paragraph.extend(block_lines)

            # Each block is a natural paragraph boundary
            if current_paragraph:
                paragraphs.append(" ".join(current_paragraph))
                current_paragraph = []

        if current_paragraph:
            paragraphs.append(" ".join(current_paragraph))

        return "\n\n".join(paragraphs)

    @staticmethod
    def _heading_prefix(font_size: float) -> Optional[str]:
        for threshold, prefix in _HEADING_PREFIXES:
            if font_size >= threshold:
                return prefix
        return None

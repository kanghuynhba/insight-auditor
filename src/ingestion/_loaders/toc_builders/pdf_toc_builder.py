# src/infrastructure/loaders/toc_builders/pdf_toc_builder.py
"""Builds a hierarchical TOC from a PDF document.

Mirrors EpubTocBuilder: the single public entry-point is ``build()``,
which returns a fake-root ``TocNode`` (level 0) whose children are the
real top-level TOC entries.  Two strategies are tried in order:

1. **Embedded outline** – ``doc.get_toc()`` returns the PDF's own
   bookmark tree when present.
2. **Heuristic scan** – if no outline exists, every page is scanned for
   unusually large text spans that look like headings.

``TocNode`` is used directly throughout — no intermediate DTO needed.
``href`` carries the 1-based page number as a string so the text
extractor can slice the document without any PDF-specific types leaking
into the shared domain model.
"""

import logging
from typing import List, Optional, Tuple
from uuid import uuid4

import fitz

from src.domain.toc_node import TocNode

logger = logging.getLogger(__name__)

# Font-size thresholds for the heuristic heading detector.
_HEADING_THRESHOLDS: List[Tuple[float, int]] = [
    (20.0, 1),
    (16.0, 2),
    (13.0, 3),
]


class PdfTocBuilder:
    """Extracts a hierarchical TOC from a PDF document."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @classmethod
    def build(cls, doc: fitz.Document) -> TocNode:
        """Return a fake-root TocNode (level 0) wrapping all TOC entries.

        Mirrors ``EpubTocBuilder.build()``: always returns a root even
        when no outline is found.
        """
        nodes = cls._try_embedded_outline(doc)
        if not nodes:
            logger.warning("PdfTocBuilder: no embedded outline found, using heuristic")
            nodes = cls._build_from_heuristic(doc)

        logger.debug("PdfTocBuilder: TOC built with %d root nodes", len(nodes))

        return TocNode(
            id="fake_root",
            title="Root",
            level=0,
            order=0,
            href="",
            children=nodes,
        )

    # ------------------------------------------------------------------
    # Strategy 1 – embedded PDF outline
    # ------------------------------------------------------------------

    @classmethod
    def _try_embedded_outline(cls, doc: fitz.Document) -> List[TocNode]:
        """Parse ``doc.get_toc()`` into a TocNode tree."""
        raw: List[Tuple[int, str, int]] = doc.get_toc()
        if not raw:
            return []
        return cls._build_tree(raw)

    @classmethod
    def _build_tree(cls, toc: List[Tuple[int, str, int]]) -> List[TocNode]:
        """Convert the flat (level, title, page) list into a proper TocNode tree.

        Uses a stack to reconstruct nesting from PyMuPDF's flat outline,
        identical to the old _build_tree_from_pdf_toc logic.
        """
        root: List[TocNode] = []
        stack: List[TocNode] = []

        for level, title, page in toc:
            node = TocNode(
                id=str(uuid4()),
                title=title,
                level=level,
                order=0,  # filled in during flattening
                href=str(page),  # 1-based page number encoded as href
            )
            while stack and stack[-1].level >= level:
                stack.pop()
            if stack:
                stack[-1].children.append(node)
            else:
                root.append(node)
            stack.append(node)

        return root

    # ------------------------------------------------------------------
    # Strategy 2 – heuristic heading scan
    # ------------------------------------------------------------------

    @classmethod
    def _build_from_heuristic(cls, doc: fitz.Document) -> List[TocNode]:
        """Walk every page and treat large-font spans as section headings.

        Sections span from their detected heading to the next one.
        An implicit "Introduction" section is emitted for any content
        that precedes the first detected heading.
        """
        nodes: List[TocNode] = []
        pending_title = "Introduction"
        pending_page = 1

        for page_num in range(doc.page_count):
            page = doc[page_num]
            for block in page.get_text("dict").get("blocks", []):
                if block.get("type") != 0:  # text blocks only
                    continue
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = span["text"].strip()
                        if not text:
                            continue
                        level = cls._heading_level(span["size"])
                        if level and 2 < len(text) < 100:
                            nodes.append(cls._make_node(pending_title, 1, pending_page))
                            pending_title = text
                            pending_page = page_num + 1  # convert to 1-based

        # Flush the last pending section
        nodes.append(cls._make_node(pending_title, 1, pending_page))
        return nodes

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_node(title: str, level: int, page: int) -> TocNode:
        return TocNode(
            id=str(uuid4()),
            title=title,
            level=level,
            order=0,
            href=str(page),  # 1-based page number encoded as href
        )

    @staticmethod
    def _heading_level(font_size: float) -> Optional[int]:
        for threshold, level in _HEADING_THRESHOLDS:
            if font_size >= threshold:
                return level
        return None

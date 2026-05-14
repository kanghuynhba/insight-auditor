# src/infrastructure/loaders/toc_builders/epub_toc_builder.py
import logging
from typing import List, Optional
from xml.etree import ElementTree as ET
from uuid import uuid4

import ebooklib
from ebooklib import epub

from src.core.toc_node import TocNode

logger = logging.getLogger(__name__)


class EpubTocBuilder:
    """Extracts a hierarchical TOC from an EPUB book."""

    _NCX_NS = {"ncx": "http://www.daisy.org/z3986/2005/ncx/"}

    @classmethod
    def build(cls, epub_book: epub.EpubBook) -> TocNode:
        """Return a fake root TocNode containing all TOC nodes as children."""
        nodes = cls._try_ncx(epub_book)
        if not nodes:
            logger.warning("EpubLoader: no TOC found, using fallback")
            nodes = cls._build_fallback_toc(epub_book)

        logger.debug(f"EpubTocBuilder: TOC built with {len(nodes)} root nodes")

        # Create fake root node
        fake_root = TocNode(
            id="fake_root",
            title="Root",
            level=0,
            order=0,
            href="",
            children=nodes,
        )
        return fake_root

    @classmethod
    def _try_ncx(cls, epub_book: epub.EpubBook) -> List[TocNode]:
        ncx_items = list(epub_book.get_items_of_type(ebooklib.ITEM_NAVIGATION))
        if not ncx_items:
            return []

        try:
            root = ET.fromstring(ncx_items[0].get_content())
        except ET.ParseError as exc:
            logger.warning("EpubTocBuilder: NCX parse error – %s", exc)
            return []

        nav_map = root.find(".//ncx:navMap", cls._NCX_NS)
        if nav_map is None:
            return []

        nodes: List[TocNode] = []
        for np in nav_map.findall("./ncx:navPoint", cls._NCX_NS):
            node = cls._parse_ncx_navpoint(np, 1)
            if node:
                nodes.append(node)
        return nodes

    @classmethod
    def _parse_ncx_navpoint(cls, np: ET.Element, level: int) -> Optional[TocNode]:
        title_elem = np.find("./ncx:navLabel/ncx:text", cls._NCX_NS)
        title = (title_elem.text or "").strip() if title_elem is not None else ""
        content_elem = np.find("./ncx:content", cls._NCX_NS)
        href = (content_elem.get("src") or "") if content_elem is not None else ""

        if not title:
            title = cls._title_from_href(href) or "Untitled"

        children = []
        for np_child in np.findall("./ncx:navPoint", cls._NCX_NS):
            child = cls._parse_ncx_navpoint(np_child, level + 1)
            if child:
                children.append(child)

        return TocNode(
            id=str(uuid4()),
            title=title,
            level=level,
            order=0,  # Will be set during flattening
            href=href,
            children=children,
        )

    @staticmethod
    def _title_from_href(href: str) -> str:
        stem = href.split("#")[0].split("/")[-1]
        for ext in (".xhtml", ".html", ".htm"):
            if stem.lower().endswith(ext):
                stem = stem[: -len(ext)]
                break
        return stem.replace("_", " ").replace("-", " ").strip()

    @classmethod
    def _build_fallback_toc(cls, epub_book: epub.EpubBook) -> List[TocNode]:
        """Create a single TOC node covering the whole book."""
        for item in epub_book.get_items():
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                href = item.file_name
                break
        else:
            href = ""

        return [
            TocNode(
                id=str(uuid4()),
                title="Full Book",
                level=1,
                order=0,
                href=href or "",
                children=[],
            )
        ]

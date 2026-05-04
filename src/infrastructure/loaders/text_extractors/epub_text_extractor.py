# # src/infrastructure/loaders/text_extractors/epub_text_extractor.py
# import logging
# import copy
# from typing import Dict, Optional
# from bs4 import BeautifulSoup, Tag
# from ebooklib import epub
# import ebooklib

# from src.infrastructure.loaders.common.markdown_converter import html_to_markdown
# from src.infrastructure.loaders.toc_builders.epub_toc_builder import EpubTocBuilder

# logger = logging.getLogger(__name__)


# class EpubTextExtractor:
#     @classmethod
#     def extract_texts(cls, epub_book: epub.EpubBook) -> Dict[str, str]:
#         """Extract sections referenced in TOC, plus chapter-level content."""
#         # First, collect all anchors from the TOC
#         toc_anchors = EpubTocBuilder.get_anchors_by_file()

#         # Build file path to item map
#         file_item_map = cls._build_file_item_map(epub_book)
#         content_map = {}

#         # Process files that have TOC references
#         for file_path, anchors in toc_anchors.items():
#             item = file_item_map.get(file_path)
#             if not item:
#                 logger.warning("No content item for %r", file_path)
#                 continue

#             try:
#                 html = item.get_content().decode("utf-8", errors="replace")
#             except Exception as e:
#                 logger.warning("Could not decode %r – %s", file_path, e)
#                 continue

#             soup = BeautifulSoup(html, "html.parser")

#             # FIRST: Extract chapter-level content (text before first section)
#             chapter_content = cls._extract_chapter_content(soup)
#             if chapter_content:
#                 chapter_key = file_path  # e.g., "chapter1.xhtml"
#                 content_map[chapter_key] = chapter_content
#                 logger.debug(f"Extracted chapter content: {chapter_key}")

#             # THEN: Extract each anchored section from this file
#             for anchor in anchors:
#                 target = soup.find(id=anchor) or soup.find("a", {"name": anchor})
#                 if not target:
#                     logger.warning("Anchor '%s' not found in %s", anchor, file_path)
#                     continue

#                 # Extract using DFS (process children first)
#                 cls._dfs_extract(target, file_path, anchor, content_map)

#         return content_map

#     @classmethod
#     def _extract_chapter_content(cls, soup: BeautifulSoup) -> str:
#         """
#         Extract content that belongs to the chapter level (before any sections).
#         This includes the main heading and any paragraphs or elements before the first <section>.
#         """
#         # Find the first section (if any)
#         first_section = soup.find("section")

#         if first_section:
#             # Collect all elements before the first section
#             elements_before = []
#             for elem in soup.body.children if soup.body else soup.children:
#                 if elem == first_section:
#                     break
#                 if hasattr(elem, "name") and elem.name not in (
#                     "nav",
#                     "script",
#                     "style",
#                 ):
#                     elements_before.append(elem)
#                 elif isinstance(elem, str) and elem.strip():
#                     # Text nodes
#                     elements_before.append(elem)
#         else:
#             # No sections at all, take everything except navigation
#             elements_before = [
#                 elem
#                 for elem in (soup.body.children if soup.body else soup.children)
#                 if hasattr(elem, "name")
#                 and elem.name != "nav"
#                 or (isinstance(elem, str) and elem.strip())
#             ]

#         if not elements_before:
#             return ""

#         # Build HTML from collected elements
#         chapter_html = "".join(str(e) for e in elements_before)
#         raw_text = html_to_markdown(chapter_html) or ""
#         return raw_text

#     @classmethod
#     def _dfs_extract(
#         cls, element: Tag, file_path: str, anchor: str, content_map: Dict[str, str]
#     ) -> None:
#         """
#         DFS extraction: process inner sections first, then extract parent.
#         Only extracts the specific anchor element, not every section.
#         """
#         # Find direct child sections (for recursion)
#         child_sections = [
#             child
#             for child in element.children
#             if hasattr(child, "name") and child.name == "section"
#         ]

#         # Process each child section recursively FIRST (deepest first)
#         for child in child_sections:
#             child_anchor = child.get("id") or child.get("name")
#             if child_anchor:
#                 child_full_href = cls.make_full_href(file_path, child_anchor)
#                 if child_full_href not in content_map:
#                     cls._dfs_extract(child, file_path, child_anchor, content_map)

#         # After processing children, extract this section
#         element_clone = copy.copy(element)

#         # Remove all nested sections from the clone (they've already been extracted)
#         for nested in element_clone.find_all("section", recursive=True):
#             nested.decompose()

#         # Convert to HTML and then to Markdown
#         section_html = str(element_clone)
#         raw_text = html_to_markdown(section_html) or ""
#         full_href = cls.make_full_href(file_path, anchor)
#         content_map[full_href] = raw_text
#         logger.debug(f"Extracted section: {full_href}")

#     @staticmethod
#     def make_full_href(file_path: str, anchor: Optional[str]) -> str:
#         """Combine file_path and anchor into a full href."""
#         if anchor:
#             return f"{file_path}#{anchor}"
#         return file_path

#     @staticmethod
#     def _build_file_item_map(epub_book: epub.EpubBook) -> Dict[str, object]:
#         """Map normalized file path to ebooklib item."""
#         mapping = {}
#         for item in epub_book.get_items():
#             if item.get_type() not in (ebooklib.ITEM_DOCUMENT, ebooklib.ITEM_UNKNOWN):
#                 continue
#             fn: str = item.file_name or ""
#             if not fn:
#                 continue
#             clean = fn
#             while clean.startswith(("./", "../")):
#                 clean = clean[2:]
#             clean = clean.lstrip("/")
#             mapping[clean] = item
#         return mapping
# src/infrastructure/loaders/text_extractors/epub_text_extractor.py
import logging
import copy
from typing import Dict, Optional, Set
from bs4 import BeautifulSoup, Tag
from ebooklib import epub
import ebooklib

from src.core.toc_node import TocNode
from src.infrastructure.loaders.common.markdown_converter import html_to_markdown

logger = logging.getLogger(__name__)


class EpubTextExtractor:
    @classmethod
    def extract_texts(
        cls, epub_book: epub.EpubBook, toc_root: TocNode
    ) -> Dict[str, str]:
        """
        Extract sections referenced in TOC, plus chapter-level content.
        Uses TocNode tree to collect all hrefs and anchors.
        """
        # First, collect all hrefs and anchors from the TOC tree
        hrefs_with_anchors = cls._collect_hrefs_from_toc(toc_root)

        # Also collect chapter-level hrefs (without anchors)
        chapter_hrefs = cls._collect_chapter_hrefs(toc_root)

        # Build file path to item map
        file_item_map = cls._build_file_item_map(epub_book)
        content_map = {}

        # Process chapter-level content first
        for href in chapter_hrefs:
            file_path = href.split("#")[0] if "#" in href else href
            item = file_item_map.get(file_path)
            if not item:
                logger.warning("No content item for chapter %r", href)
                continue

            try:
                html = item.get_content().decode("utf-8", errors="replace")
            except Exception as e:
                logger.warning("Could not decode %r – %s", file_path, e)
                continue

            soup = BeautifulSoup(html, "html.parser")
            chapter_content = cls._extract_chapter_content(soup)
            if chapter_content:
                content_map[href] = chapter_content
                logger.debug(f"Extracted chapter content: {href}")

        # Process anchored sections
        for href, anchor in hrefs_with_anchors:
            file_path = href.split("#")[0]
            item = file_item_map.get(file_path)
            if not item:
                logger.warning("No content item for %r", href)
                continue

            try:
                html = item.get_content().decode("utf-8", errors="replace")
            except Exception as e:
                logger.warning("Could not decode %r – %s", href, e)
                continue

            soup = BeautifulSoup(html, "html.parser")

            # Find the anchor element
            target = soup.find(id=anchor) or soup.find("a", {"name": anchor})
            if not target:
                logger.warning("Anchor '%s' not found in %s", anchor, file_path)
                continue

            # Extract using DFS (process children first)
            cls._dfs_extract(target, href, anchor, content_map)

        return content_map

    @classmethod
    def _collect_hrefs_from_toc(cls, node: TocNode) -> list:
        """
        Traverse TocNode tree and collect all (full_href, anchor) pairs.
        Returns list of tuples: [(full_href, anchor), ...]
        """
        hrefs = []

        # Skip fake root (level 0)
        if node.level > 0 and node.href and "#" in node.href:
            parts = node.href.split("#")
            file_path = parts[0]
            anchor = parts[1] if len(parts) > 1 else None
            if anchor:
                hrefs.append((node.href, anchor))

        # Recursively collect from children
        for child in node.children:
            hrefs.extend(cls._collect_hrefs_from_toc(child))

        return hrefs

    @classmethod
    def _collect_chapter_hrefs(cls, node: TocNode) -> Set[str]:
        """
        Traverse TocNode tree and collect chapter-level hrefs (without anchors).
        These are for content that belongs to the chapter itself.
        """
        hrefs = set()

        # Skip fake root (level 0)
        if node.level > 0 and node.href:
            # If href has no anchor, it's a chapter-level reference
            if "#" not in node.href:
                hrefs.add(node.href)

        # Recursively collect from children
        for child in node.children:
            hrefs.update(cls._collect_chapter_hrefs(child))

        return hrefs

    @classmethod
    def _extract_chapter_content(cls, soup: BeautifulSoup) -> str:
        """
        Extract content that belongs to the chapter level (before any sections).
        This includes the main heading and any paragraphs or elements before the first <section>.
        """
        # Find the first section (if any)
        first_section = soup.find("section")

        if first_section:
            # Collect all elements before the first section
            elements_before = []
            for elem in soup.body.children if soup.body else soup.children:
                if elem == first_section:
                    break
                if hasattr(elem, "name") and elem.name not in (
                    "nav",
                    "script",
                    "style",
                ):
                    elements_before.append(elem)
                elif isinstance(elem, str) and elem.strip():
                    # Text nodes
                    elements_before.append(elem)
        else:
            # No sections at all, take everything except navigation
            elements_before = [
                elem
                for elem in (soup.body.children if soup.body else soup.children)
                if hasattr(elem, "name")
                and elem.name != "nav"
                or (isinstance(elem, str) and elem.strip())
            ]

        if not elements_before:
            return ""

        # Build HTML from collected elements
        chapter_html = "".join(str(e) for e in elements_before)
        raw_text = html_to_markdown(chapter_html) or ""
        return raw_text

    @classmethod
    def _dfs_extract(
        cls, element: Tag, full_href: str, anchor: str, content_map: Dict[str, str]
    ) -> None:
        """
        DFS extraction: process inner sections first, then extract parent.
        Only extracts the specific anchor element, not every section.
        """
        # Find direct child sections (for recursion)
        child_sections = [
            child
            for child in element.children
            if hasattr(child, "name") and child.name == "section"
        ]

        # Process each child section recursively FIRST (deepest first)
        for child in child_sections:
            child_anchor = child.get("id") or child.get("name")
            if child_anchor:
                # Reconstruct full href for child
                file_path = full_href.split("#")[0]
                child_full_href = cls.make_full_href(file_path, child_anchor)
                if child_full_href not in content_map:
                    cls._dfs_extract(child, child_full_href, child_anchor, content_map)

        # After processing children, extract this section
        element_clone = copy.copy(element)

        # Remove all nested sections from the clone (they've already been extracted)
        for nested in element_clone.find_all("section", recursive=True):
            nested.decompose()

        # Convert to HTML and then to Markdown
        section_html = str(element_clone)
        raw_text = html_to_markdown(section_html) or ""
        content_map[full_href] = raw_text
        logger.debug(f"Extracted section: {full_href}")

    @staticmethod
    def make_full_href(file_path: str, anchor: Optional[str]) -> str:
        """Combine file_path and anchor into a full href."""
        if anchor:
            return f"{file_path}#{anchor}"
        return file_path

    @staticmethod
    def _build_file_item_map(epub_book: epub.EpubBook) -> Dict[str, object]:
        """Map normalized file path to ebooklib item."""
        mapping = {}
        for item in epub_book.get_items():
            if item.get_type() not in (ebooklib.ITEM_DOCUMENT, ebooklib.ITEM_UNKNOWN):
                continue
            fn: str = item.file_name or ""
            if not fn:
                continue
            clean = fn
            while clean.startswith(("./", "../")):
                clean = clean[2:]
            clean = clean.lstrip("/")
            mapping[clean] = item
        return mapping

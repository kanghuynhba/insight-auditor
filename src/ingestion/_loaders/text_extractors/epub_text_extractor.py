import logging
import copy
from typing import Dict, Optional, List, Tuple
from bs4 import BeautifulSoup, Tag, NavigableString
from ebooklib import epub
import ebooklib

from src.domain.toc_node import TocNode
from src.ingestion._loaders.common.markdown_converter import html_to_markdown

logger = logging.getLogger(__name__)


class EpubTextExtractor:
    # Tags to skip entirely during sibling extraction
    SKIP_TAGS = {"nav", "script", "style"}
    # Tags considered as containers for section-container mode
    CONTAINER_TAGS = {"section", "article", "div", "main", "aside", "body"}
    # Heading tags
    HEADING_TAGS = {"h", "h1", "h2", "h3", "h4", "h5", "h6"}

    @classmethod
    def extract_texts(
        cls, epub_book: epub.EpubBook, toc_root: TocNode
    ) -> Dict[str, str]:
        """
        Extract sections referenced in TOC using frontend-aligned extraction logic.
        Returns a dict mapping full href (e.g. 'OEBPS/ch01.xhtml#sec1') to Markdown.

        Stop-anchor logic mirrors the frontend's findStopAnchor in useNavigationMap.ts:
        for each node, scan forward in the FLAT navigation list and use the first
        subsequent node that shares the same file (and is not a descendant) as the
        hard stop — regardless of heading level or parent/child relationship.
        """
        file_item_map = cls._build_file_item_map(epub_book)
        content_map: Dict[str, str] = {}

        # Build a flat list of all TOC nodes (mirrors frontend's flatten())
        flat_nodes: List[TocNode] = cls._flatten_toc(toc_root)

        # Build a set of descendant IDs for each node (for stop-anchor filtering)
        descendant_ids_map: Dict[str, set] = {
            node.id: cls._descendant_ids(node) for node in flat_nodes
        }

        for idx, node in enumerate(flat_nodes):
            if not node.href:
                continue

            full_href = node.href
            file_path, anchor = cls._split_href(full_href)

            item = file_item_map.get(file_path)
            if not item:
                logger.warning("No content item for %r", file_path)
                continue

            try:
                html = item.get_content().decode("utf-8", errors="replace")
            except Exception as e:
                logger.warning("Could not decode %r – %s", file_path, e)
                continue

            soup = BeautifulSoup(html, "html.parser")

            # Compute stop anchor using frontend-aligned flat-list logic
            stop_anchor = cls._find_stop_anchor(
                flat_nodes, idx, node, descendant_ids_map
            )

            if anchor:
                target = cls._find_anchor(soup, anchor)
                if not target:
                    logger.warning("Anchor '%s' not found in %s", anchor, file_path)
                    continue
                extracted_html = cls._extract_by_target(
                    soup, target, file_path, stop_anchor
                )
            else:
                # No anchor → chapter-level extraction (stop anchor not applicable)
                extracted_html = cls._extract_chapter_level(soup)

            if extracted_html:
                markdown = html_to_markdown(extracted_html) or ""
                if markdown.strip():
                    content_map[full_href] = markdown
                    logger.debug("Extracted %s (%d chars)", full_href, len(markdown))

        return content_map

    @classmethod
    def _flatten_toc(cls, node: TocNode) -> List[TocNode]:
        """Return every non-root node in depth-first order."""
        result = []
        if node.level > 0:
            result.append(node)
        for child in node.children:
            result.extend(cls._flatten_toc(child))
        return result

    @classmethod
    def _descendant_ids(cls, node: TocNode) -> set:
        """Return descendant node IDs."""
        ids = set()
        for child in node.children:
            ids.add(child.id)
            ids.update(cls._descendant_ids(child))
        return ids

    @classmethod
    def _find_stop_anchor(
        cls,
        flat_nodes: List[TocNode],
        idx: int,
        current: TocNode,
        descendant_ids_map: Dict[str, set],
    ) -> Optional[str]:
        """
        Mirrors frontend findStopAnchor() in useNavigationMap.ts exactly:

        Scan forward from idx+1 in the flat node list.
        - Stop scanning if we reach a node in a DIFFERENT file.
        - Skip nodes that are descendants of `current`.
        - Return the anchor of the first qualifying node.

        This means the stop is always the very next peer/uncle/cousin in the
        same file — regardless of heading level or TOC depth.
        """
        current_file = cls._split_href(current.href)[0]
        descendant_ids = descendant_ids_map.get(current.id, set())

        for i in range(idx + 1, len(flat_nodes)):
            candidate = flat_nodes[i]
            candidate_file = cls._split_href(candidate.href)[0]

            # Different file → stop searching (no stop anchor in this file)
            if candidate_file != current_file:
                break

            # Skip own descendants
            if candidate.id in descendant_ids:
                continue

            # First non-descendant node in same file → its anchor is our stop
            _, candidate_anchor = cls._split_href(candidate.href)
            if candidate_anchor:
                return candidate_anchor

        return None

    # -------------------------------------------------------------------------
    #  Frontend-aligned extraction methods
    # -------------------------------------------------------------------------

    @classmethod
    def _extract_chapter_level(cls, soup: BeautifulSoup) -> str:
        """
        Mimics frontend extractChapterLevel:
        - If there's a <section>, take everything before it (excluding skippable tags).
        - Otherwise clone <body>, remove nav/script/style/section, return inner HTML.
        """
        body = soup.body
        if not body:
            return ""

        first_section = body.find("section", recursive=False)
        if first_section:
            parts = []
            for child in body.children:
                if child == first_section:
                    break
                if isinstance(child, Tag):
                    if child.name in cls.SKIP_TAGS:
                        continue
                    parts.append(str(child))
                elif isinstance(child, NavigableString) and child.strip():
                    parts.append(child.strip())
            return "".join(parts)

        clone = copy.copy(body)
        for tag in clone.find_all(["nav", "script", "style", "section"]):
            tag.decompose()
        return "".join(str(c) for c in clone.children)

    @classmethod
    def _extract_by_target(
        cls,
        soup: BeautifulSoup,
        target: Tag,
        file_path: str,
        stop_anchor: Optional[str],
    ) -> str:
        """
        Dispatches to the right extraction strategy based on the target element,
        now passing the pre-computed stop_anchor from the flat navigation map.

        Mirrors the frontend extract() dispatcher but stop_anchor is always
        supplied from the nav map rather than computed from the DOM.
        """
        tag = target.name.lower()

        # 1. Body → chapter level
        if tag == "body":
            return cls._extract_chapter_level(soup)

        # 2. Container (section/div/article/…) → section-container mode:
        #    clone it and strip nested <section> children.
        #    stop_anchor is NOT used here because the container is self-contained.
        if tag in cls.CONTAINER_TAGS:
            clone = copy.copy(target)
            for nested in clone.find_all("section", recursive=True):
                nested.decompose()
            return str(clone)

        # 3. Heading or heading-like → sibling-walk with nav-map stop anchor
        if tag in cls.HEADING_TAGS or cls._is_heading_like(target):
            heading = target
        else:
            heading = cls._resolve_heading_element(target, soup.body)
            if not heading:
                return cls._extract_siblings(target, stop_anchor)

        return cls._extract_siblings(heading, stop_anchor)

    @classmethod
    def _extract_siblings(cls, start_el: Tag, stop_anchor: Optional[str]) -> str:
        """
        Collects outerHTML from start_el and its following siblings,
        skipping SKIP_TAGS, stopping when an element with id=stop_anchor
        is reached (or found inside an element).

        Mirrors frontend extractSiblings() exactly.
        """
        parts = []
        cur: Optional[Tag] = start_el

        while cur:
            if stop_anchor:
                if cur.get("id") == stop_anchor:
                    break
                if cur.find(id=stop_anchor):
                    clone = copy.copy(cur)
                    cls._trim_to_stop_anchor(clone, stop_anchor)
                    if clone.name not in cls.SKIP_TAGS:
                        parts.append(str(clone))
                    break

            if cur.name not in cls.SKIP_TAGS:
                parts.append(str(cur))

            # Advance to next sibling Tag (skip NavigableString)
            cur = cur.next_sibling
            while cur is not None and not isinstance(cur, Tag):
                cur = cur.next_sibling

        return "".join(parts)

    @classmethod
    def _trim_to_stop_anchor(cls, clone: Tag, stop_anchor: str) -> None:
        """
        Removes all content at and after the element with id=stop_anchor
        from the cloned tag. Mirrors frontend trimToStopAnchor().
        """
        stop_el = clone.find(id=stop_anchor)
        if not stop_el:
            return

        node = stop_el
        while node and node != clone:
            sib = node.next_sibling
            while sib:
                next_sib = sib.next_sibling
                if hasattr(sib, "decompose"):
                    sib.decompose()
                sib = next_sib
            node = node.parent

        stop_el.decompose()

    # -------------------------------------------------------------------------
    #  Helper methods
    # -------------------------------------------------------------------------

    @staticmethod
    def _find_anchor(soup: BeautifulSoup, anchor: str) -> Optional[Tag]:
        """Find element by id or name attribute."""
        el = soup.find(id=anchor)
        if not el:
            el = soup.find("a", {"name": anchor})
        return el

    @classmethod
    def _resolve_heading_element(cls, el: Tag, body: Optional[Tag]) -> Optional[Tag]:
        """
        Mirrors frontend resolveHeadingElement():
        - If el itself is heading-like, return it.
        - Else try parent, then next sibling.
        - Else fall back to nearest block ancestor.
        """
        tag = el.name.lower()
        if tag in cls.HEADING_TAGS or cls._is_heading_like(el):
            return el

        parent = el.parent
        if (
            parent
            and parent.name
            and (parent.name in cls.HEADING_TAGS or cls._is_heading_like(parent))
        ):
            return parent

        nxt = el.next_sibling
        while nxt and not isinstance(nxt, Tag):
            nxt = nxt.next_sibling
        if nxt and (nxt.name in cls.HEADING_TAGS or cls._is_heading_like(nxt)):
            return nxt

        return cls._nearest_block_ancestor(el, body)

    @classmethod
    def _nearest_block_ancestor(cls, el: Tag, root: Optional[Tag]) -> Optional[Tag]:
        BLOCK_TAGS = {
            "div",
            "p",
            "section",
            "article",
            "aside",
            "main",
            "header",
            "footer",
            "li",
            "td",
            "th",
            "blockquote",
            "figure",
        }
        cur = el.parent
        while cur and cur != root:
            if cur.name in BLOCK_TAGS:
                return cur
            cur = cur.parent
        return None

    @classmethod
    def _is_heading_like(cls, el) -> bool:
        if not isinstance(el, Tag) or el.name != "p":
            return False
        classes = el.get("class", [])
        if isinstance(classes, str):
            classes = classes.split()
        heading_hints = {"h", "chap", "chapter-title", "section-title"}
        return any(hint in " ".join(classes).lower() for hint in heading_hints)

    # -------------------------------------------------------------------------
    #  TOC traversal and file helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def _split_href(href: str) -> Tuple[str, Optional[str]]:
        """Return (file_path, anchor) – anchor may be None."""
        if "#" in href:
            parts = href.split("#", 1)
            return parts[0], parts[1]
        return href, None

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

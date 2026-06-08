"""TOC tree construction for ingestion."""

from __future__ import annotations

from typing import Any, Optional

from src.domain.section import Section
from src.domain.toc_node import TocNode
from src.ingestion._models import TocNodeModel


class TOCService:
    @staticmethod
    def to_tree(
        toc_data: list[dict[str, Any]], sections: list[Any] | None = None
    ) -> Optional[TocNodeModel]:
        """Return an immutable fake-root TOC model."""
        if not toc_data:
            return None

        toc_node_root = TOCService.from_book_toc(toc_data, sections)
        if not toc_node_root:
            return None
        return TOCService._to_model(toc_node_root)

    @staticmethod
    def to_toc_node_tree(
        toc_data: list[dict[str, Any]], sections: list[Any] | None = None
    ) -> Optional[TocNode]:
        """Convert stored TOC JSON to the mutable internal tree representation."""
        return TOCService.from_book_toc(toc_data, sections)

    @staticmethod
    def to_book_toc(root_node: TocNode, book_id: str) -> list[dict[str, Any]]:
        """Serialize a fake-root TOC tree for Book.table_of_content JSON."""
        if not root_node or not root_node.children:
            return []

        return TOCService._serialize_nodes(root_node.children, book_id, 0)[0]

    @staticmethod
    def from_book_toc(
        toc_data: list[dict[str, Any]], sections: list[Any] | None = None
    ) -> Optional[TocNode]:
        """Build a fake-root TocNode tree from Book.table_of_content JSON."""
        if not toc_data:
            return None

        sections_by_id = {
            section.id: section
            for section in sections or []
            if getattr(section, "id", None) is not None
        }
        root = TocNode(
            id="fake_root",
            title="Root",
            section_id="",
            level=0,
            order=0,
            section=None,
            children=[],
        )
        root.children = [
            TOCService._node_from_json(item, sections_by_id) for item in toc_data
        ]
        return root

    @staticmethod
    def _to_model(node: TocNode) -> TocNodeModel:
        return TocNodeModel(
            id=node.id,
            title=node.title,
            level=node.level,
            order=node.order,
            section_id=node.section_id,
            href=node.href,
            children=[TOCService._to_model(child) for child in node.children],
        )

    @staticmethod
    def _serialize_nodes(
        nodes: list[TocNode], book_id: str, current_order: int
    ) -> tuple[list[dict[str, Any]], int]:
        data: list[dict[str, Any]] = []
        next_order = current_order

        for node in nodes:
            next_order += 1
            node_order = next_order
            section_id = node.section_id or (
                node.section.id if node.section is not None else None
            )

            if node.section is None:
                node.section = (
                    Section(id=section_id, raw_text="")
                    if section_id
                    else Section(raw_text="")
                )
                section_id = node.section.id
                node.section_id = section_id

            if node.section:
                node.section.book_id = book_id
                node.section.title = node.title
                node.section.level = node.level
                node.section.order = node_order
                node.section.href = node.href
                section_id = node.section.id

            children, next_order = TOCService._serialize_nodes(
                node.children, book_id, next_order
            )
            data.append(
                {
                    "id": node.id,
                    "section_id": section_id,
                    "href": node.href,
                    "level": node.level,
                    "order": node_order,
                    "children": children,
                }
            )

        return data, next_order

    @staticmethod
    def _node_from_json(
        item: dict[str, Any], sections_by_id: dict[str, Any]
    ) -> TocNode:
        section_id = item.get("section_id")
        section = sections_by_id.get(section_id)
        title = getattr(section, "title", "") or item.get("title") or ""
        node = TocNode(
            id=item["id"],
            title=title,
            section_id=section_id,
            href=item.get("href"),
            level=item["level"],
            order=item["order"],
            section=section,
            children=[],
        )
        node.children = [
            TOCService._node_from_json(child, sections_by_id)
            for child in item.get("children", [])
        ]
        return node

# src/services/toc_service.py
"""TOC service – converts between flat DB entities and hierarchical business objects.

Changes from the original
-------------------------
* :meth:`to_tree` now returns a :class:`~src.model.toc_node_model.TocNodeModel`
  (an immutable service model) instead of a mutable ``TocNode`` dataclass.
  Internally the service still builds the ``TocNode`` tree for efficiency (the
  tree-walking algorithm does not change), and then delegates to the converter.
* All other public and private methods are unchanged.

The ``TocNode`` dataclass remains in ``src/core/`` for internal use by this
service and :class:`~src.services.chunk_ingestion_service.ChunkIngestionService`.
"""

from __future__ import annotations

from typing import List, Optional

from src.converter.entity_to_model import toc_node_to_model
from src.core.table_of_content import TableOfContent
from src.core.toc_node import TocNode
from src.model.toc_node_model import TocNodeModel


class TOCService:
    """Service for converting between ``TableOfContent`` entities and the
    ``TocNode`` / ``TocNodeModel`` representations.

    *Direction 1*: ``List[TableOfContent]`` → :class:`~src.model.toc_node_model.TocNodeModel`
    *Direction 2*: :class:`~src.core.toc_node.TocNode` → ``List[TableOfContent]``
    """

    # ------------------------------------------------------------------
    # Direction 1: List[TableOfContent] → TocNodeModel (public API)
    # ------------------------------------------------------------------

    @staticmethod
    def to_tree(entities: List[TableOfContent]) -> Optional[TocNodeModel]:
        """Convert a flat list of :class:`~src.core.table_of_content.TableOfContent`
        entities to a single tree rooted at a virtual root node.

        The returned value is an **immutable** :class:`~src.model.toc_node_model.TocNodeModel`
        – safe to pass across service boundaries and into routers.

        Args:
            entities: Flat list of ORM entities, typically from
                      ``book.table_of_contents``.

        Returns:
            The virtual root model, or ``None`` when ``entities`` is empty.
        """
        if not entities:
            return None

        # 1. Build the internal TocNode tree (unchanged algorithm)
        toc_node_root = TOCService._build_toc_node_tree(entities)

        # 2. Convert the internal tree to an immutable service model
        return toc_node_to_model(toc_node_root)

    # ------------------------------------------------------------------
    # Direction 1 – internal: build mutable TocNode tree
    # ------------------------------------------------------------------

    @staticmethod
    def _build_toc_node_tree(entities: List[TableOfContent]) -> TocNode:
        """Build a ``TocNode`` tree from sorted entities and return the fake root."""
        sorted_entities = sorted(entities, key=lambda x: x.order)

        root = TocNode(
            id="fake_root",
            title="Root",
            section_id="",
            level=0,
            order=0,
            section=None,
            children=[],
        )
        root.children = TOCService._build_children(sorted_entities, 0, 0)
        return root

    @staticmethod
    def _build_children(
        entities: List[TableOfContent], parent_level: int, start_index: int
    ) -> List[TocNode]:
        """Recursively build children nodes using DFS based on level transitions."""
        children = []
        i = start_index

        while i < len(entities):
            current = entities[i]

            if current.level == parent_level + 1:
                node = TocNode(
                    id=current.id,
                    title=current.title,
                    level=current.level,
                    section_id=current.section_id,
                    href=current.href,
                    order=current.order,
                    section=current.section,
                    children=[],
                )
                node.children, next_index = TOCService._build_children_with_index(
                    entities, current.level, i + 1
                )
                children.append(node)
                i = next_index if next_index > i + 1 else i + 1

            elif current.level <= parent_level:
                break
            else:
                i += 1

        return children

    @staticmethod
    def _build_children_with_index(
        entities: List[TableOfContent], parent_level: int, start_index: int
    ) -> tuple[List[TocNode], int]:
        """Build children nodes and return the next index to process."""
        children = []
        i = start_index

        while i < len(entities):
            current = entities[i]

            if current.level == parent_level + 1:
                node = TocNode(
                    id=current.id,
                    title=current.title,
                    section_id=current.section_id,
                    href=current.href,
                    level=current.level,
                    order=current.order,
                    section=current.section,
                    children=[],
                )
                node.children, next_idx = TOCService._build_children_with_index(
                    entities, current.level, i + 1
                )
                children.append(node)
                i = next_idx if next_idx > i + 1 else i + 1

            elif current.level <= parent_level:
                break
            else:
                i += 1

        return children, i

    # ------------------------------------------------------------------
    # Direction 2: TocNode (with fake root) → List[TableOfContent]
    # ------------------------------------------------------------------

    @staticmethod
    def to_entities(root_node: TocNode, book_id: str) -> List[TableOfContent]:
        """Convert a single tree (with fake root) to a flat list of
        :class:`~src.core.table_of_content.TableOfContent` entities.

        Skips the fake root node itself.

        Args:
            root_node: The virtual root produced by a loader or
                       :meth:`_build_toc_node_tree`.
            book_id:   The parent book ID to embed in each entity.

        Returns:
            A flat, ordered list of ``TableOfContent`` ORM entities ready for
            persistence.
        """
        if not root_node or not root_node.children:
            return []

        entities: List[TableOfContent] = []
        TOCService._flatten_tree(root_node.children, book_id, entities, 0)
        return entities

    @staticmethod
    def _flatten_tree(
        nodes: List[TocNode],
        book_id: str,
        entities: List[TableOfContent],
        current_order: int,
    ) -> int:
        """Recursively flatten a ``TocNode`` tree into ``TableOfContent`` entities.

        Returns:
            The next available order number after processing all nodes.
        """
        next_order = current_order

        for node in nodes:
            next_order += 1
            entity = TableOfContent(
                id=node.id,
                book_id=book_id,
                section_id=node.section_id,
                section=node.section,
                href=node.href,
                level=node.level,
                order=next_order,
                title=node.title,
            )
            entities.append(entity)

            if node.children:
                next_order = TOCService._flatten_tree(
                    node.children, book_id, entities, next_order
                )

        return next_order

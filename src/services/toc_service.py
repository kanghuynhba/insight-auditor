# src/services/toc_service.py
from typing import List, Optional
from src.core.table_of_content import TableOfContent
from src.core.toc_node import TocNode


class TOCService:
    """Service for converting between TableOfContent entities and TocNode business objects."""

    # Direction 1: List[TableOfContent] → TocNode (with fake root)
    @staticmethod
    def to_tree(entities: List[TableOfContent]) -> Optional[TocNode]:
        """
        Convert flat list of TableOfContent entities to a single tree with fake root.
        Returns a virtual root node containing all top-level chapters as children.
        """
        if not entities:
            return None

        # Sort by order to maintain reading sequence
        sorted_entities = sorted(entities, key=lambda x: x.order)

        # Create fake root
        root = TocNode(
            id="fake_root",
            title="Root",
            level=0,
            order=0,
            section=None,
            children=[],
        )

        # Build children using DFS
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

    # Direction 2: TocNode (with fake root) → List[TableOfContent]
    @staticmethod
    def to_entities(root_node: TocNode, book_id: str) -> List[TableOfContent]:
        """
        Convert a single tree (with fake root) to flat list of TableOfContent entities.
        Skips the fake root node itself.
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
        """
        Recursively flatten TocNode tree into TableOfContent entities.
        Returns the next available order number after processing all nodes.
        """
        next_order = current_order

        for node in nodes:
            # Increment order for this node
            next_order += 1

            # Create TableOfContent entity from TocNode
            entity = TableOfContent(
                id=node.id,
                book_id=book_id,
                section_id=node.section_id,
                section=node.section,
                level=node.level,
                order=next_order,
                title=node.title,
            )
            entities.append(entity)

            # Recursively flatten children and update next_order
            if node.children:
                next_order = TOCService._flatten_tree(
                    node.children, book_id, entities, next_order
                )

        return next_order

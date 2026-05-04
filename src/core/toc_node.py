# src/core/toc_node.py
from typing import List, Optional
from dataclasses import dataclass, field
from src.core.section import Section


@dataclass
class TocNode:
    """Business object for TOC operations - used internally throughout the system.
    WHY THIS EXISTS:
    - TableOfContent (ORM model) stores TOC as a FLAT list with (title, order, level)
    - This flat representation is efficient for storage but difficult to work with
    - TocNode converts the flat list into a TREE structure (hierarchy with parent/children)
    - Services use TocNode for tree operations (traversal, searching, modification)
    - Convert back to TableOfContent when persisting to database
    """

    id: str
    title: str
    level: int
    order: int
    href: Optional[str] = None
    section: Optional[Section] = None
    children: List["TocNode"] = field(default_factory=list)

    @property
    def is_chapter(self) -> bool:
        return self.level == 1

    @property
    def has_children(self) -> bool:
        return len(self.children) > 0

    @property
    def has_content(self) -> bool:
        return self.section is not None and self.section.raw_text is not None

    def get_all_sections(self) -> List[Section]:
        """Get all sections in this subtree (depth-first)."""
        sections = []
        if self.section:
            sections.append(self.section)
        for child in self.children:
            sections.extend(child.get_all_sections())
        return sections

    def get_all_nodes(self) -> List["TocNode"]:
        """Get all nodes in this subtree (depth-first)."""
        nodes = [self]
        for child in self.children:
            nodes.extend(child.get_all_nodes())
        return nodes

    def find_node(self, node_id: str) -> Optional["TocNode"]:
        """Find a node by ID in this subtree."""
        if self.id == node_id:
            return self
        for child in self.children:
            found = child.find_node(node_id)
            if found:
                return found
        return None

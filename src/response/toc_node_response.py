# src/response/toc_node_response.py
from typing import List, Optional

from src.core.toc_node import TocNode
from src.response.base import BaseSchema


class TocNodeResponse(BaseSchema):
    id: str
    title: str
    level: int
    order: int
    children: List["TocNodeResponse"] = []

    @classmethod
    def from_toc_node(cls, toc_node: "TocNode") -> "TocNodeResponse":
        """Convert business object to API response."""
        return cls(
            id=toc_node.id,
            title=toc_node.title,
            level=toc_node.level,
            order=toc_node.order,
            children=[cls.from_toc_node(child) for child in toc_node.children],
        )

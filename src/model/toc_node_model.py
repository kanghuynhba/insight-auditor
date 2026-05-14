# src/model/toc_node_model.py
"""Service model for a TOC node – the immutable internal API contract."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class TocNodeModel(BaseModel):
    """Immutable service model representing one node in the table-of-contents tree.

    Produced by :func:`src.converter.entity_to_model.toc_node_to_model` and
    consumed by routers, which convert it further to :class:`TocNodeResponse`.
    """

    id: str
    title: str
    level: int
    order: int
    section_id: Optional[str] = None
    href: Optional[str] = None
    children: List["TocNodeModel"] = []

    model_config = {"frozen": True}

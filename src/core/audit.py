# src/core/audit.py

from datetime import datetime
from typing import List, Optional
from sqlmodel import JSON, Column, Field
from core.entity import Entity
from core.helpers import now


class AuditReport(Entity, table=True):
    __tablename__ = "audit_report"
    summary_id: str = Field(foreign_key="summary.id", index=True)
    section_id: str = Field(foreign_key="section.id", index=True)
    score: float = 0.0
    # list of fact IDs
    mastered: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    # list of fact IDs
    omissions: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    # list of fact IDs
    misconceptions: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    score_delta: Optional[float] | None = None
    generated_at: datetime = Field(default_factory=now)

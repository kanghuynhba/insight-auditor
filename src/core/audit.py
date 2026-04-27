# src/core/audit.py

from datetime import datetime
from typing import List, Optional
from sqlmodel import JSON, Column, Field, Relationship
from src.core.entity import Entity
from src.core.fact_validation import FactValidationResult
from src.core.helpers import now


class AuditReport(Entity, table=True):
    __tablename__ = "audit_report"
    section_id: str = Field(foreign_key="section.id", index=True)
    summary_id: str = Field(foreign_key="summary.id", index=True)
    score: float = 0.0
    score_delta: float | None = None
    generated_at: datetime = Field(default_factory=now)
    summary: Optional["Summary"] = Relationship(back_populates="audit_reports")
    validations: List["FactValidationResult"] = Relationship(
        back_populates="report",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )

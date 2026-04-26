from typing import Optional
from sqlmodel import TEXT, Column, Field, Relationship

# from src.core.atomic_fact import AtomicFact
from src.core.entity import Entity
from src.core.enums import FactStatus


class FactValidationResult(Entity, table=True):
    __tablename__ = "fact_validation_result"
    atomic_fact_id: str = Field(foreign_key="atomic_fact.id", index=True)
    report_id: str = Field(foreign_key="audit_report.id", index=True)
    status: FactStatus
    evidence: Optional[str] = Field(default=None, sa_column=Column(TEXT, nullable=True))
    confidence: float
    improved: Optional[bool] = None

    report: Optional["AuditReport"] = Relationship(back_populates="validations")
    # atomic_fact: Optional["AtomicFact"] = Relationship(back_populates="validations")

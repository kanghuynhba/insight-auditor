from datetime import datetime
from typing import List, Optional
from sqlmodel import Field, Relationship
from src.core.audit import AuditReport
from src.core.entity import Entity
from src.core.helpers import now, word_count


class Summary(Entity, table=True):
    __tablename__ = "summary"
    section_id: str = Field(foreign_key="section.id", index=True)
    text: str
    attempt_number: int = 1
    submitted_at: datetime = Field(default_factory=now)
    section: Optional["Section"] = Relationship(back_populates="summaries")

    audit_reports: List["AuditReport"] = Relationship(back_populates="summary")

    @property
    def word_count(self) -> int:
        return word_count(self.text)

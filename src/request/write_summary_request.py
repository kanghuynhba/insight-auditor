"""Command object for submitting a user-written summary for evaluation."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, field_validator


class WriteSummaryRequest(BaseModel):
    """Command to evaluate a user-written summary against a section's atomic facts.

    ``summary_text`` is the full plain-text summary the user wrote.  Minimum
    word-count enforcement is delegated to
    :class:`~src.audit.AuditGateway`, which reads the
    ``min_summary_words`` setting.
    """

    section_id: Optional[str] = None
    summary_text: str

    @field_validator("section_id")
    @classmethod
    def section_id_not_blank(cls, v: Optional[str]) -> Optional[str]:
        """Ensure section_id is a non-empty string."""
        if v is None:
            return None
        if not v or not v.strip():
            raise ValueError("section_id must not be blank")
        return v.strip()

    @field_validator("summary_text")
    @classmethod
    def summary_text_not_blank(cls, v: str) -> str:
        """Ensure the summary contains at least some text."""
        if not v or not v.strip():
            raise ValueError("summary_text must not be blank")
        return v

    model_config = {"frozen": True}

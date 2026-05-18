"""Command object for submitting a user-written summary for evaluation."""

from __future__ import annotations

from pydantic import BaseModel, field_validator


class WriteSummaryRequest(BaseModel):
    """Command to evaluate a user-written summary against a section's atomic facts.

    ``section_id`` is available as a URL path parameter; it is included here
    so the command object is self-contained and testable in isolation.

    ``summary_text`` is the full plain-text summary the user wrote.  Minimum
    word-count enforcement is delegated to
    :class:`~src.services.audit_service.AuditService`, which reads the
    ``min_summary_words`` setting.
    """

    section_id: str
    summary_text: str

    @field_validator("section_id")
    @classmethod
    def section_id_not_blank(cls, v: str) -> str:
        """Ensure section_id is a non-empty string."""
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

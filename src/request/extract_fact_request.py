"""Command object for starting a fact-extraction job."""

from __future__ import annotations

from pydantic import BaseModel, field_validator


class ExtractFactRequest(BaseModel):
    """Command to enqueue an async fact-extraction job for a section.

    ``section_id`` is also available as a URL path parameter; it is included
    here for command completeness so callers that build the command object
    before sending the HTTP request have a single source of truth.

    ``force`` instructs the service to delete pre-existing facts before
    re-extracting.  When ``False`` (default) the service skips chunks that
    already have facts, making repeated calls cheap.
    """

    section_id: str
    force: bool = False

    @field_validator("section_id")
    @classmethod
    def section_id_not_blank(cls, v: str) -> str:
        """Ensure section_id is a non-empty string."""
        if not v or not v.strip():
            raise ValueError("section_id must not be blank")
        return v.strip()

    model_config = {"frozen": True}

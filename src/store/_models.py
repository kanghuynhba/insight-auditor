"""Models returned by the store module."""

from __future__ import annotations

from pydantic import BaseModel


class DeleteBookResultModel(BaseModel):
    book_id: str
    deleted_sections: int = 0
    deleted_summaries: int = 0
    deleted_reports: int = 0
    deleted_facts: int = 0

    model_config = {"frozen": True}

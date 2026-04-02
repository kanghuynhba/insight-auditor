# src/core/section.py

from pydantic import BaseModel, Field, field_validator, model_validator

from src.core.helpers import _new_id

class Section(BaseModel):
    id: str = Field(default_factory=_new_id)
    book_id: str
    chapter_id: str
    # "001.002.003"
    path_id: str
    # "001.002"
    parent_path_id: str | None
    title: str
    raw_text: str
    level: int
    chunk_ids: list[str]=[]
    word_count: int=0

    # TODO Need to understand this
    @model_validator(mode="after")
    def compute_word_count(self) -> "Section":
        if self.word_count == 0 and self.raw_text:
            count = len(self.raw_text.split())
            # Standard assignment fails on frozen models, so we bypass:
            object.__setattr__(self, "word_count", count)
        return self

    model_config = {"frozen": True}

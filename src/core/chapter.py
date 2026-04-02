# src/core/chapter.py

from pydantic import BaseModel, Field, field_validator, model_validator

from src.core.helpers import _new_id

class Chapter(BaseModel):
    id: str = Field(default_factory=_new_id)
    book_id: str
    title: str
    # If there are Section inside Chapter
    path_id: str
    index: int
    sections: list[Section] = Field(default_factory=list)
    # LLM-generated of this chapter
    structural_map: str | None = None

    @field_validator("index")
    @classmethod
    def index_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("Chapter index must be >= 0")
        return v

    model_config = {"frozen": True}

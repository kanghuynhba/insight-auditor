from pydantic import BaseModel, Field, field_validator, model_validator
from src.core.helpers import _new_id

class Chapter(BaseModel):
    id: str = Field(default_factory=_new_id)
    book_id: str
    # If there are Section inside Chapter
    parent_id: str | None = None
    # level 1, 2, 3,...
    level: int = 1
    title: str
    index: int
    raw_text: str
    chunk_ids: list[str] = Field(default_factory=list)
    word_count: int = 0

    @field_validator("index")
    @classmethod
    def index_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("Chapter index must be >= 0")
        return v

    # TODO Need to understand this
    @model_validator(mode="after")
    def compute_word_count(self) -> "Chapter":
        if self.word_count == 0 and self.raw_text:
            count = len(self.raw_text.split())
            # Standard assignment fails on frozen models, so we bypass:
            object.__setattr__(self, "word_count", count)
        return self

    model_config = {"frozen": True}

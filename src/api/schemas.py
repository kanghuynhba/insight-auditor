# src/api/schemas.py

from pydantic import BaseModel, ConfigDict
from typing import List, Optional

class BaseSchema(BaseModel):
    """ Base schema with common configuration for FastAPI responses. """
    model_config = ConfigDict(from_attributes=True)

class ChapterResponse(BaseSchema):
    id: str
    book_id: str
    title: Optional[str]
    index: int
    word_count: int

class BookResponse(BaseSchema):
    id: str
    title: str
    author: Optional[str]
    format: str
    chapters: List[ChapterResponse]


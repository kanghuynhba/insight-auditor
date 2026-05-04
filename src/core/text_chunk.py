# src/core/text_chunk.py

from typing import Any, Optional

from lancedb.pydantic import LanceModel, Vector
from pydantic import Field, model_validator
from src.core.helpers import new_id


class TextChunk(LanceModel):
    """Represents a strictly sized slice of text ready for vector embedding."""

    id: str = Field(default_factory=new_id)
    book_id: str
    section_id: str
    text: str
    chunk_index: int  # position within the section
    chunk_level: str  # "paragraph" | "sentence" | "word_window"
    word_count: int = 0
    start_char: int
    end_char: int
    context_text: Optional[str] = None
    vector: Optional[Vector(1536)] = None

    model_config = {"frozen": True}

    @model_validator(mode="before")
    @classmethod
    def calculate_word_count(cls, data: Any) -> Any:
        """
        Calculates the word count before the model freezes,
        if it wasn't explicitly provided.
        """
        # Ensure we are working with a dictionary of inputs
        if isinstance(data, dict):
            # If word_count is missing or 0, calculate it from the text
            if not data.get("word_count") and data.get("text"):
                data["word_count"] = len(data["text"].split())

        return data

# src/core/helpers.py

from datetime import datetime, timezone
from uuid import uuid4


def new_id() -> str:
    return str(uuid4())


def now() -> datetime:
    return datetime.now(timezone.utc)


def word_count(text: str | None) -> int:
    """Return the number of words in a text, or 0 if None/empty."""
    if not text:
        return 0
    return len(text.split())

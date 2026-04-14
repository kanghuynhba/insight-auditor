# src/core/helpers.py

from datetime import datetime, timezone
from uuid import uuid4


# Helpers
def new_id() -> str:
    return str(uuid4())


def now() -> datetime:
    return datetime.now(timezone.utc)

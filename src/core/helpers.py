# src/core/helpers.py

from uuid import uuid4
from datetime import datetime, timezone

# Helpers
def _new_id() -> str:
    return str(uuid4())

def _now() -> datetime:
    return datetime.now(timezone.utc)



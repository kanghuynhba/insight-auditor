# src/core/job_store.py
"""Simple in-memory job store shared across services.

This module provides a lightweight, thread-safe (async-safe) dictionary that
services use to track the lifecycle of background tasks (extraction jobs,
ingestion jobs, etc.) without requiring a persistent job queue.

Usage::

    from src.core.job_store import JobStore

    store = JobStore()

    # In the service that starts a job:
    async with store.lock:
        store[job_id] = {"status": "pending", ...}

    # In the background task that runs the job:
    async with store.lock:
        store[job_id]["status"] = "running"

The store is intentionally **not** a singleton so each service can own its
own instance; inject it via DI if you want a shared store across services.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Iterator, Optional


class JobStore:
    """Async-safe in-memory store for job metadata dictionaries.

    Each entry is a plain ``dict`` with at minimum the keys:
    ``status``, ``progress``, ``created_at``, ``section_id``.

    The ``lock`` attribute is an :class:`asyncio.Lock` that callers *must*
    hold when reading or writing entries to avoid race conditions.
    """

    def __init__(self) -> None:
        self._data: Dict[str, Dict[str, Any]] = {}
        self.lock: asyncio.Lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # dict-like interface (NOT lock-guarded – acquire lock before calling)
    # ------------------------------------------------------------------

    def __setitem__(self, job_id: str, value: Dict[str, Any]) -> None:
        self._data[job_id] = value

    def __getitem__(self, job_id: str) -> Dict[str, Any]:
        return self._data[job_id]

    def __contains__(self, job_id: object) -> bool:
        return job_id in self._data

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def get(
        self, job_id: str, default: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        return self._data.get(job_id, default)

    def update_field(self, job_id: str, field: str, value: Any) -> None:
        """Convenience method – update a single field inside an existing entry.

        *Not* lock-guarded; acquire ``self.lock`` before calling.
        """
        if job_id not in self._data:
            raise KeyError(f"Job {job_id!r} not found in store")
        self._data[job_id][field] = value

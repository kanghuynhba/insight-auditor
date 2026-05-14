# src/model/__init__.py
"""Service models (internal API contracts between services and routers).

These are immutable Pydantic ``BaseModel`` classes (``frozen=True``).
They are **never** exposed directly as HTTP responses; routers convert them
to the appropriate response DTOs in ``src/response/``.
"""

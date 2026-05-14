# main.py
import logging
from fastapi.staticfiles import StaticFiles
from pathlib import Path

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

from fastapi import FastAPI
from src.core.config import get_settings
from src.infrastructure.adapters.mariadb.database_context import DatabaseContext
from src.api.routers import books, sections
from fastapi.middleware.cors import CORSMiddleware

# audit router is deprecated; keep only if needed for backward compatibility
# from src.api.routers import audit

settings = get_settings()

app = FastAPI(title="Insight Auditor API", version="3.0")

# after creating app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or ["*"] for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(books.router)
app.include_router(sections.router)  # new sections router

# Optionally keep audit router for legacy endpoints (e.g., /audit/...)
# but mark as deprecated. For now, we'll keep it but you can remove later.
# app.include_router(audit.router)


@app.get("/")
async def root():
    return {"message": "Insight Auditor API is running (v3.0)"}


@app.on_event("startup")
async def init_db():
    db = DatabaseContext(str(settings.mariadb_url))
    await db.initialize_database()


# Directory where extracted books will be stored
EXTRACTED_BOOKS_DIR = Path("extracted_books")
EXTRACTED_BOOKS_DIR.mkdir(exist_ok=True)

app.mount(
    "/extracted",
    StaticFiles(directory=str(EXTRACTED_BOOKS_DIR)),
    name="extracted_books",
)

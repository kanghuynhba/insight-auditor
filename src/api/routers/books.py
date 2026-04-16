# src/api/books.py

from typing import List

from fastapi import APIRouter, Depends, UploadFile
from pydantic import BaseModel
from src.api.schemas import BookResponse, ChapterResponse

router = APIRouter(prefix="/books", tags=["books"])


@router.post("/", response_model=BookResponse)
async def update_book(
    file: UploadFile,
    svc: IngestionService = Depends(get_ingestion_svc),
):
    """Upload or create a new book"""
    pass

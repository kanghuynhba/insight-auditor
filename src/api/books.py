# src/api/books.py

from fastapi import APIRouter, Depends, UploadFile
from typing import List

from src.api.schemas import BookResponse, ChapterResponse
from pydantic import BaseModel

router = APIRouter(prefix="/books", tags=["books"])

@router.post("/", response_model=BookResponse)
async def update_book(
    file: UploadFile,
    svc: IngestionService=Depends(get_ingestion_svc),
    storage: StorageService=Depends(get_storage_svc),
):
    """ Upload or create a new book """
    pass



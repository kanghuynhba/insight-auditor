# src/api/dependencies.py

from fastapi import Depends

from src.services.storage import StorageService
from src.services.ingestion import IngestionService

def get_storage_svc() -> StorageService:
    return StorageService()

def get_ingestion_svc():
    return IngestionService()


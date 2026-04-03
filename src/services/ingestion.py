# src/services/ingestion.py
import os
from pathlib import Path

from src.core.enums import FileFormat


class IngestionService:
    def __init__(self, settings: Settings):
        _settings = settings

    def _load(self, path: Path, fmt: FileFormat) -> Book:
        if fmt == FileFormat.PDF:
            return PdfLoader(seft._settings).load(path)
        return EpubLoader(seft._settings).load(path)

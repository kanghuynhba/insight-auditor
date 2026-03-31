# src/services/ingestion.py
import os
from src.core.enums import FileFormat
from pathlib import Path
from dotenv import load_dotenv()

class IngestionService:
    def __init__():
        _settings=

    def _load(self, path: Path, fmt: FileFormat):
        if fmt==FileFormat.PDF:
            return PdfLoader(seft._settings).load(path)
        return EpubLoader(seft._settings).load(path)


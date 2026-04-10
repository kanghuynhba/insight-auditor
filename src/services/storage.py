# src/services/storage.py
import os
from pathlib import Path
from uuid import uuid4

import aiofiles
from fastapi import UploadFile
from src.infrastructure.loader.file_type import FileType


class StorageService:
    def __init__(self, uploads_dir: str | Path = "uploads"):
        self._uploads_dir = Path(uploads_dir)
        self._uploads_dir.mkdir(parents=True, exist_ok=True)

    async def save_upload(self, file: UploadFile) -> Path:
        # Validate file format
        fmt = self.validate_extension(file.filename)

        # Generate a unique, secure destination path
        safe_filename = f"{uuid4()}_{file.filename}"
        dest = self._uploads_dir / safe_filename

        # Stream the file to disk in 1MB chunks to prevent memory overload
        async with aiofiles.open(dest, "wb") as f:
            # Read chunks of 1024 * 1024 bytes (1MB)
            while chunk := await file.read(1024 * 1024):
                await f.write(chunk)

        return dest

    def validate_extension(self, filename: str | None) -> "FileType":
        return FileType.from_filename(filename)

# api/storage.py
import aiofiles
import tempfile
from pathlib import Path


async def save_upload(file: UploadFile) -> Path:
    # Use a temporary file (or your configured uploads_dir)
    upload_dir = Path("./uploads")
    upload_dir.mkdir(exist_ok=True)
    temp_path = upload_dir / file.filename
    async with aiofiles.open(temp_path, "wb") as f:
        content = await file.read()
        await f.write(content)
    return temp_path

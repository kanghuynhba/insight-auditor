import asyncio
import io
from fastapi import UploadFile
from src.services.storage import StorageService

async def run_test():
    print("1. Initializing StorageService...")
    # We will use a separate test folder so we don't clutter your real uploads
    storage = StorageService(uploads_dir="test_uploads")

    print("2. Creating a fake PDF file in memory...")
    # This simulates the bytes FastAPI receives from a user's web browser
    fake_file_content = b"%PDF-1.4... (Imagine this is a massive PDF book) ..."
    fake_file = io.BytesIO(fake_file_content)

    # Wrap it in FastAPI's UploadFile object
    upload_file = UploadFile(filename="test_book.pdf", file=fake_file)

    print("3. Testing save_upload()...")
    try:
        saved_path = await storage.save_upload(upload_file)
        print(f"\n✅ SUCCESS! File saved to: {saved_path}")

        # 4. Double check that the file actually exists on the hard drive
        if saved_path.exists():
            print(f"✅ Verified: The file was found on the disk.")
            with open(saved_path, "rb") as f:
                print(f"✅ Verified: File contents read as -> {f.read()}")
        else:
            print("❌ Error: The script finished, but the file is missing from the drive.")

    except Exception as e:
        print(f"\n❌ FAILED with error: {e}")

if __name__ == "__main__":
    # Because save_upload is 'async', we need asyncio to run it in a standard script
    asyncio.run(run_test())

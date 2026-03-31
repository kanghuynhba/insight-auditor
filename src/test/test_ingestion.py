# test_ingestion.py
from pathlib import Path
from src.core.config import get_settings
from src.infrastructure.loaders.pdf_loader import PdfLoader

def run_test(file_path: str):
    # 1. Load Settings (Automatically reads your .env)
    settings = get_settings()

    # 2. Initialize the Loader
    loader = PdfLoader(settings)

    # 3. Process the PDF
    path = Path(file_path)
    if not path.exists():
        print(f"❌ Error: File {file_path} not found.")
        return

    print(f"--- 📖 Processing: {path.name} ---")
    book, chapters = loader.load(path)

    # 4. Inspect the results
    print(f"\n✅ SUCCESS: Book Created")
    print(f"ID: {book.id}")
    print(f"Title: {book.title}")
    print(f"Format: {book.source_format}")
    print(f"Total Chapters: {book.total_chapters}")
    print(f"Ingested At: {book.ingested_at}")

    print(f"\n--- 📑 Chapter Breakdown ---")
    for ch in chapters:
        # Show first 100 characters of text to verify extraction
        preview = ch.raw_text[:100].replace('\n', ' ')
        print(f"[{ch.index}] {ch.title:.<30} | Words: {ch.word_count:<5} | Preview: {preview}...")

if __name__ == "__main__":
    # Change 'test_book.pdf' to whatever PDF you have handy
    run_test("ai_engineering.pdf")

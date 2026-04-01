# test_ingestion.py
from pathlib import Path
from src.core.config import get_settings
from src.infrastructure.loaders.pdf_loader import PdfLoader

def run_test(file_path: str):
    # 1. Load Settings
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

    # 4. Inspect Book Metadata
    print(f"\n✅ SUCCESS: Book Created")
    print(f"ID: {book.id}")
    print(f"Title: {book.title}")
    print(f"Total Chapters/Sections: {book.total_chapters}")

    print(f"\n--- 📑 Hierarchical Breakdown ---")
    print(f"{'Index':<7} | {'Level':<5} | {'Title & Parent Info':<50} | {'Words'}")
    print("-" * 85)

    # Create a quick ID -> Title map for parent visualization
    id_to_title = {ch.id: ch.title for ch in chapters}

    for ch in chapters:
        # Create indentation based on level
        indent = "  " * (ch.level - 1)
        prefix = "┗━ " if ch.level > 1 else "MAIN "

        # Format parent info
        parent_info = ""
        if ch.parent_id:
            p_title = id_to_title.get(ch.parent_id, "Unknown")
            parent_info = f" (Parent: {p_title[:20]}...)"

        display_title = f"{indent}{prefix}{ch.title}"

        # Print row
        print(f"[{ch.index:03}] | L{ch.level:<4} | {display_title:<50} | {ch.word_count}")

        # Optional: Print a tiny preview for deep levels to verify text
        if ch.level > 2:
            preview = ch.raw_text[:60].replace('\n', ' ')
            print(f"{' ':13} | {' ':5} | {indent}   预览: {preview}...")

if __name__ == "__main__":
    run_test("src/test/ai_engineering.pdf")

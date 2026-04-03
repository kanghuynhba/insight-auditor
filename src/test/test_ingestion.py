# src/test/test_ingestion.py
import sys
from pathlib import Path

# Force project root into the system path so imports work from the terminal
root_dir = Path(__file__).resolve().parents[2]
sys.path.append(str(root_dir))

from src.core.config import get_settings
from src.infrastructure.loaders.pdf_loader import PdfLoader


def run_test(file_path: str):
    settings = get_settings()
    loader = PdfLoader(settings)

    path = Path(file_path)
    if not path.exists():
        print(f"❌ Error: File '{file_path}' not found.")
        return

    print(f"\n{'='*85}")
    print(f"📖 INGESTING: {path.name}")
    print(f"{'='*85}\n")

    # 1. Extract the single Aggregate Root
    book = loader.load(path)

    # 2. Print Top-Level Metadata
    print("📚 BOOK METADATA")
    print("-" * 50)
    print(f"Title:          {book.title}")
    print(
        f"Source Format:  {book.source_format.value if hasattr(book.source_format, 'value') else book.source_format}"
    )
    print(f"Total Chapters: {book.total_chapters}")
    print(f"Book ID:        {book.id}")
    print("-" * 50)
    print("\n📑 HIERARCHICAL TABLE OF CONTENTS\n")

    # 3. Print the Tree Structure
    print(f"{'PATH ID':<12} │ {'STRUCTURE & CONTENT'}")
    print(f"{'─'*12}┼{'─'*72}")

    for chapter in book.chapters:
        # Chapter Row (Level 1)
        print(f"{chapter.path_id:<12} │ 📂 CHAPTER: {chapter.title.upper()}")

        # Section Rows (Level 2+)
        for i, sec in enumerate(chapter.sections):
            # Calculate depth for indentation (e.g., '001.002.001' -> depth 3 -> indent 2)
            depth = len(sec.path_id.split("."))
            indent = "  " * (depth - 1)

            # Use a corner branch '└──' for the last item, otherwise '├──'
            is_last = i == len(chapter.sections) - 1
            branch = "└──" if is_last else "├──"

            # Word count fallback (in case your Pydantic validator didn't run yet)
            words = getattr(sec, "word_count", len(sec.raw_text.split()))

            # Truncate section title if it's too long
            clean_title = sec.title[:45] + "..." if len(sec.title) > 45 else sec.title

            print(
                f"{sec.path_id:<12} │ {indent}{branch} 📄 {clean_title} ({words} words)"
            )

            # Text Snippet underneath the section
            if sec.raw_text:
                snippet = sec.raw_text[:70].replace("\n", " ").strip()
                # Draw a vertical line '│' if it's not the last item in the chapter to connect the tree
                vertical_line = "│" if not is_last else " "
                print(
                    f"{' '*12} │ {indent}{vertical_line}      [Snippet]: {snippet}..."
                )

        # Visual spacer between chapters
        print(f"{' '*12} │")

    print(f"{'='*85}")
    print("✅ Extraction Complete.\n")


if __name__ == "__main__":
    # Ensure this path matches where you put your test PDF!
    run_test("src/test/introduction_to_algorithms.pdf")

#!/usr/bin/env python3
import sys
from pathlib import Path

# Add the project root to path so that 'src' can be found
sys.path.insert(0, str(Path(__file__).parent))


# Create a dummy Settings class that the loader expects but never uses
class DummySettings:
    pass


# Monkey-patch the config module before importing PdfLoader
import types

fake_config = types.ModuleType("src.core.config")
fake_config.Settings = DummySettings
sys.modules["src.core.config"] = fake_config

# Now import PdfLoader – it will find the fake config
from src.infrastructure.loaders.pdf_loader import PdfLoader


def main():
    # Allow passing a PDF file path as first argument, otherwise use default
    if len(sys.argv) > 1:
        pdf_path = Path(sys.argv[1])
    else:
        pdf_path = Path("uploads/ai_engineering.pdf")

    if not pdf_path.exists():
        print(f"Error: {pdf_path} not found")
        sys.exit(1)

    print(f"Loading {pdf_path} ...")
    loader = PdfLoader(DummySettings())  # dummy settings
    book = loader.load(pdf_path)

    print(f"Title: {book.title}")
    print(f"Author: {book.author}")
    print(f"Total TOC entries: {len(book.toc)}")

    output_dir = Path("output_markdown")
    output_dir.mkdir(exist_ok=True)

    for toc_entry in book.toc:
        section = toc_entry.section
        if section and section.raw_text:
            safe_title = section.title.replace("/", "_").replace("\\", "_")
            filename = f"{section.path_id}_{safe_title}.md"
            filepath = output_dir / filename
            filepath.write_text(section.raw_text, encoding="utf-8")
            print(f"Saved: {filepath.name}")
        else:
            print(f"Skipped (no content): {toc_entry.title}")


if __name__ == "__main__":
    main()

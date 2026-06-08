#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.domain.config import get_settings
from src.ingestion._loaders import PdfLoader
from src.ingestion._toc import TOCService


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
    loader = PdfLoader(get_settings())
    extracted = loader.extract_raw(pdf_path)
    book_id = loader.get_stable_id(pdf_path)
    toc_data = TOCService.to_book_toc(extracted.toc_root, book_id)
    sections = extracted.toc_root.get_all_sections()

    print(f"Title: {extracted.title}")
    print(f"Author: {extracted.author}")
    print(f"Total TOC entries: {len(toc_data)}")

    output_dir = Path("output_markdown")
    output_dir.mkdir(exist_ok=True)

    for section in sections:
        if section.raw_text:
            safe_title = section.title.replace("/", "_").replace("\\", "_")
            filename = f"{section.order:04d}_{safe_title}.md"
            filepath = output_dir / filename
            filepath.write_text(section.raw_text, encoding="utf-8")
            print(f"Saved: {filepath.name}")
        else:
            print(f"Skipped (no content): {section.title}")


if __name__ == "__main__":
    main()

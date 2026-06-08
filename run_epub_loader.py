#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.domain.config import get_settings
from src.ingestion._loaders import EpubLoader
from src.ingestion._toc import TOCService


def collect_all_sections(root_toc):
    """Traverse the TOC tree and yield all attached sections."""
    if root_toc.section and root_toc.level > 0:  # skip dummy root (level 0)
        yield root_toc.section
    for child in root_toc.children:
        yield from collect_all_sections(child)


def main():
    epub_path = Path("uploads/clean_architecture.epub")
    if not epub_path.exists():
        print(f"Error: {epub_path} not found")
        sys.exit(1)

    print(f"Loading {epub_path} ...")

    loader = EpubLoader(get_settings())
    extracted = loader.extract_raw(epub_path)
    book_id = loader.get_stable_id(epub_path)
    toc_data = TOCService.to_book_toc(extracted.toc_root, book_id)
    sections = collect_all_sections(extracted.toc_root)

    print(f"Title: {extracted.title}")
    print(f"Author: {extracted.author}")

    if not toc_data:
        print("No TOC found.")
        return

    all_sections = list(sections)
    print(f"Total sections with content: {len(all_sections)}")

    for section in all_sections:
        if section.raw_text:
            print(f"{section.title} -> {section.href}")
        else:
            print(f"Skipped (no text): {section.title}")


if __name__ == "__main__":
    main()

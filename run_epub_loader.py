#!/usr/bin/env python3
import sys
from pathlib import Path

# ----------------------------------------------------------------------
# Setup: dummy config to avoid real settings
# ----------------------------------------------------------------------
from src.core.config import get_settings

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))


# Create a dummy Settings class that the loader expects but never uses
class DummySettings:
    pass


# Monkey-patch the config module before importing EpubLoader
import types

fake_config = types.ModuleType("src.core.config")
fake_config.Settings = DummySettings
sys.modules["src.core.config"] = fake_config

# Now import EpubLoader – it will find the fake config
from src.infrastructure.loaders.epub_loader import EpubLoader


def collect_all_sections(root_toc):
    """Traverse the TOC tree (starting from the root) and yield all Section objects."""
    if root_toc.section and root_toc.level > 0:  # skip dummy root (level 0)
        yield root_toc.section
    for child in root_toc.children:
        yield from collect_all_sections(child)


def main():
    epub_path = Path("uploads/ddia.epub")
    if not epub_path.exists():
        print(f"Error: {epub_path} not found")
        sys.exit(1)

    print(f"Loading {epub_path} ...")
    loader = EpubLoader(get_settings())  # dummy settings
    book = loader.load(epub_path)

    print(f"Title: {book.title}")
    print(f"Author: {book.author}")

    # Now book.toc is a single root TableOfContent node (the fake root)
    if book.toc:
        all_toc_entries = list(collect_all_sections(book.toc))
        print(f"Total sections with content: {len(all_toc_entries)}")
    else:
        print("No TOC found.")
        return

    # Export each section as a Markdown file
    output_dir = Path("output_markdown")
    output_dir.mkdir(exist_ok=True)

    for section in all_toc_entries:
        if section.raw_text:
            safe_title = section.title.replace("/", "_").replace("\\", "_")
            filename = f"{safe_title}.md"
            filepath = output_dir / filename
            filepath.write_text(section.raw_text, encoding="utf-8")
            print(f"Saved: {filepath.name}")
        else:
            print(f"Skipped (no text): {section.title}")


if __name__ == "__main__":
    main()

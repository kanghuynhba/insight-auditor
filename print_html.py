from pathlib import Path

from ebooklib import epub
import ebooklib

from src.infrastructure.loaders.toc_builders.epub_toc_builder import (
    EpubTocBuilder,
    _TocNode,
)


def main():
    epub_path = Path("uploads/mock_epub.epub")
    try:
        book = epub.read_epub(str(epub_path), {"ignore_ncx": False})
    except Exception as e:
        print(f"Failed to load EPUB: {e}")
        sys.exit(1)
    EpubTocBuilder.build(book)
    toc = EpubTocBuilder._try_ncx(book)
    print(toc)


if __name__ == "__main__":
    main()

"""Loader internals owned by ingestion."""

from src.ingestion._loaders._base import ExtractedBookData, Loader
from src.ingestion._loaders._epub import EpubLoader
from src.ingestion._loaders._file_type import FileType
from src.ingestion._loaders._pdf import PdfLoader

__all__ = ["EpubLoader", "ExtractedBookData", "FileType", "Loader", "PdfLoader"]

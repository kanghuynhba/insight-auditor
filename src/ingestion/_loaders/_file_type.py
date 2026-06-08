from enum import StrEnum

from src.domain.exceptions import UnsupportedFormatError


class FileType(StrEnum):
    """enums for file types"""

    Pdf = "pdf"
    Epub = "epub"

    @classmethod
    def from_filename(cls, filename: str) -> "FileType":
        if not filename:
            raise UnsupportedFormatError("Filename is missing!")

        ext = filename.split(".")[-1].lower()

        try:
            return cls(ext)
        except ValueError:
            raise UnsupportedFormatError(
                f"Unsupport file format: '.{ext}'. Only PDF and EPUB are allowed!"
            )

# src/core/exceptions.py


class UnsupportedFormatError(Exception):
    pass


class BookNotFoundError(Exception):
    pass


class SectionNotFoundError(Exception):
    pass


class AuditGateError(Exception):
    pass


class IngestionError(Exception):
    pass


class ExtractionNotReadyError(Exception):
    """Raised when atomic facts are not ready for a section."""

    def __init__(self, status: str, message: str):
        self.status = status
        self.message = message
        super().__init__(message)

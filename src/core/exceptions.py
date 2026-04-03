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

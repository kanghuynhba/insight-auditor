"""Public fact extraction module."""

from src.extraction._facts import get_facts_by_section
from src.extraction._models import AtomicFactModel, FactsModel
from src.extraction._responses import facts_response
from src.extraction._parser import parse_fact_payload
from src.extraction._service import FactExtraction

__all__ = [
    "AtomicFactModel",
    "FactExtraction",
    "FactsModel",
    "facts_response",
    "get_facts_by_section",
    "parse_fact_payload",
]

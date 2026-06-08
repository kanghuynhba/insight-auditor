"""Response mapping for fact extraction routes."""

from src.extraction._models import FactsModel
from src.response.atomic_fact import AtomicFactResponse
from src.response.section import FactsResponse


def facts_response(model: FactsModel) -> FactsResponse:
    return FactsResponse(
        section_id=model.section_id,
        extraction_status=model.extraction_status,
        facts=[
            AtomicFactResponse(
                id=fact.id,
                point=fact.point,
                rank=fact.rank,
                reason=fact.reason,
                questions=fact.questions,
                chunk_id=fact.chunk_id,
                start_char=fact.start_char,
                end_char=fact.end_char,
            )
            for fact in model.facts
        ],
    )

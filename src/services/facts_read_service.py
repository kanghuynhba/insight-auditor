from typing import List, Optional
from src.response.atomic_fact import AtomicFactResponse
from src.response.section import FactsResponse, HintResponse
from src.core.enums import ExtractionStatus
from src.core.exceptions import ExtractionNotReadyError
from src.core.atomic_fact import AtomicFact
from src.core.section import Section
from src.infrastructure.persistence.base_repository import Repository


class FactsReadService:
    def __init__(
        self,
        fact_repo: Repository[AtomicFact] = None,
        section_repo: Repository[Section] = None,
    ):
        self.fact_repo = fact_repo
        self.section_repo = section_repo

    async def get_facts_by_section(self, section_id: str) -> FactsResponse:
        """Return formatted facts or raise ValueError with status."""
        section = await self.section_repo.find_by_id(section_id)
        if not section:
            raise ValueError(f"Section {section_id} not found")
        if section.extraction_status != ExtractionStatus.DONE:
            raise ExtractionNotReadyError(
                status=section.extraction_status,
                message="No facts extracted yet",
            )
        facts = await self.fact_repo.find_by_section(section_id)
        return FactsResponse(
            section_id=section_id,
            extraction_status=ExtractionStatus.DONE,
            facts=[AtomicFactResponse.from_atomic_fact(fact) for fact in facts],
        )

    async def get_hints(
        self,
        section_id: str,
        attempt_number: Optional[int] = None,
        max_hints: int = 5,
    ) -> List[HintResponse]:
        """Return one question per fact, prioritized by rank."""
        facts = await self.fact_repo.find_by_section(section_id)
        if not facts:
            return []

        # (Optional) filter by attempt_number – would need audit_repo
        # For now, ignore attempt_number.

        sorted_facts = sorted(facts, key=lambda f: f.rank.value)  # Critical first
        hints = []
        for fact in sorted_facts:
            if fact.questions:
                hints.append(fact.questions[0])
            if len(hints) >= max_hints:
                break

        return [HintResponse(hint=hint) for hint in hints]

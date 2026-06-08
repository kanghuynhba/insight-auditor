"""Summary-to-fact validation."""

from __future__ import annotations

import json
import logging
from typing import Any, Optional, Protocol

from pydantic import BaseModel, Field

from src.domain import AtomicFact, AuditReport, FactStatus, FactValidationResult, Summary
from src.llm.prompts.validate_summary import (
    FIRST_ATTEMPT_BLOCK,
    PREVIOUS_ATTEMPT_BLOCK,
    VALIDATION_SYSTEM,
    VALIDATION_USER,
    _FIRST_ATTEMPT_BLOCK_EXAMPLE,
    _PREVIOUS_ATTEMPT_BLOCK_EXAMPLE,
)

logger = logging.getLogger(__name__)

MIN_WORD_COUNT = 50


class CompletionClient(Protocol):
    async def async_completion(self, **kwargs: Any) -> Any: ...


class ValidationItem(BaseModel):
    fact_id: str
    status: str
    evidence: str
    confidence: float
    improved: Optional[bool] = None


class ValidationResponse(BaseModel):
    results: list[ValidationItem] = Field(alias="result")


async def validate_facts(
    llm: CompletionClient,
    summary: str,
    facts: list[AtomicFact],
    previous_summary: Optional[Summary] = None,
    previous_report: Optional[AuditReport] = None,
) -> list[FactValidationResult]:
    is_first_attempt = not (previous_summary and previous_report)

    if is_first_attempt:
        attempt_context_block = FIRST_ATTEMPT_BLOCK
    else:
        validations_str = _build_validations_str(previous_report.validations)
        attempt_context_block = PREVIOUS_ATTEMPT_BLOCK.format(
            attempt_number=previous_summary.attempt_number,
            previous_summary=previous_summary.text,
            score=round(previous_report.score, 2),
            validations=validations_str,
        )

    facts_data = [{"id": f.id, "point": f.point, "rank": f.rank.value} for f in facts]
    user_message = VALIDATION_USER.format(
        summary=summary,
        facts=json.dumps(facts_data, indent=2),
        attempt_context_block=attempt_context_block,
        first_attempt_block_example=_FIRST_ATTEMPT_BLOCK_EXAMPLE,
        previous_attempt_block_example=_PREVIOUS_ATTEMPT_BLOCK_EXAMPLE,
    )

    response = await llm.async_completion(
        messages=[
            {"role": "system", "content": VALIDATION_SYSTEM},
            {"role": "user", "content": user_message},
        ],
        response_format=ValidationResponse.model_json_schema(),
    )

    raw = response.formatted_response
    if not raw:
        return []

    results = []
    for item in raw:
        try:
            results.append(
                FactValidationResult(
                    report_id="",
                    atomic_fact_id=item["fact_id"],
                    status=FactStatus(item["status"].lower()),
                    evidence=item.get("evidence", ""),
                    confidence=float(item.get("confidence", 0.0)),
                    improved=item.get("improved"),
                )
            )
        except (KeyError, ValueError) as exc:
            logger.warning("Skipping malformed validation item: %s - %s", item, exc)

    return results


def _build_validations_str(validations: list[FactValidationResult]) -> str:
    grouped: dict[str, list[str]] = {
        "Found": [],
        "Partial": [],
        "Missing": [],
        "Contradicted": [],
    }
    for validation in validations:
        label = validation.status.value.capitalize()
        if label in grouped:
            grouped[label].append(validation.atomic_fact_id)

    lines = []
    for label, ids in grouped.items():
        id_str = ", ".join(ids) if ids else "none"
        lines.append(f"  {label:<14}{id_str}")
    return "\n".join(lines)

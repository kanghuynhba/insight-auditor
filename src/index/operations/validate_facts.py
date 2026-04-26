# validate_facts function

import logging
from litellm import json
from src.core.atomic_fact import AtomicFact
from src.core.enums import FactStatus
from src.core.fact_validation import FactValidationResult
from src.core.summary import Summary
from src.core.audit import AuditReport
from typing import Optional
from src.infrastructure.llm.completion.completion import LLMCompletion
from src.infrastructure.prompts.index.validate_summary import (
    VALIDATION_SYSTEM,
    VALIDATION_USER,
    FIRST_ATTEMPT_BLOCK,
    PREVIOUS_ATTEMPT_BLOCK,
    _FIRST_ATTEMPT_BLOCK_EXAMPLE,
    _PREVIOUS_ATTEMPT_BLOCK_EXAMPLE,
)

logger = logging.getLogger()

MIN_WORD_COUNT = 50


def _build_validations_str(validations: list[FactValidationResult]) -> str:
    """
    Render previous validations into a compact human-readable block for the prompt.
    Groups by status so the model gets a clear picture of what was right/wrong.

    Example output:
        Found:       f-001, f-002
        Partial:     f-003
        Missing:     f-004, f-005
        Contradicted: f-006
    """
    grouped: dict[str, list[str]] = {
        "Found": [],
        "Partial": [],
        "Missing": [],
        "Contradicted": [],
    }
    for v in validations:
        label = v.status.value.capitalize()
        if label in grouped:
            grouped[label].append(v.atomic_fact_id)

    lines = []
    for label, ids in grouped.items():
        id_str = ", ".join(ids) if ids else "none"
        lines.append(f"  {label:<14}{id_str}")
    return "\n".join(lines)


async def validate_facts(
    llm: "LLMCompletion",
    summary: str,
    facts: list[AtomicFact],
    previous_summary: Optional[Summary] = None,
    previous_report: Optional[AuditReport] = None,
) -> list[FactValidationResult]:

    # --- Hard guard: reject under-length summaries before touching the LLM ---
    word_count = len(summary.split())
    if word_count < MIN_WORD_COUNT:
        logger.info(
            f"Summary rejected: {word_count} words (minimum {MIN_WORD_COUNT}). "
            "Returning all facts as Missing."
        )
        return [
            FactValidationResult(
                atomic_fact_id=f.id,
                status=FactStatus.MISSING,
                evidence="",
                confidence=1.0,
                improved=None,
            )
            for f in facts
        ]

    # --- Build the attempt context block ---
    is_first_attempt = not (previous_summary and previous_report)

    if is_first_attempt:
        attempt_context_block = FIRST_ATTEMPT_BLOCK
    else:
        # Derive omissions and misconceptions from stored validations
        # instead of relying on removed list fields on AuditReport
        validations_str = _build_validations_str(previous_report.validations)
        attempt_context_block = PREVIOUS_ATTEMPT_BLOCK.format(
            attempt_number=previous_summary.attempt_number,
            previous_summary=previous_summary.text,
            score=round(previous_report.score, 2),
            validations=validations_str,
        )

    # Ordered list — model must return results in this same order
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
        response_format=list[dict],
    )

    raw = response.formatted_response
    if not raw:
        return []

    results = []
    for item in raw:
        try:
            results.append(
                FactValidationResult(
                    atomic_fact_id=item["fact_id"],
                    status=FactStatus(
                        item["status"].lower()
                    ),  # enum values are lowercase
                    evidence=item.get("evidence", ""),
                    confidence=float(item.get("confidence", 0.0)),
                    improved=item.get("improved"),  # None | True | False
                )
            )
        except (KeyError, ValueError) as e:
            logger.warning(f"Skipping malformed validation item: {item} — {e}")

    return results

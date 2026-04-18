# src/index/operations/extract_atomic_facts.py
from typing import TYPE_CHECKING, Any, Dict

from src.core.atomic_fact import AtomicFact
from src.core.enums import Tier

if TYPE_CHECKING:
    from src.infrastructure.llm.completion import LLMCompletion

import logging

logger = logging.getLogger(__name__)


def _validate_span(
    raw_fact: Dict[str, Any], text: str
) -> tuple[int | None, int | None]:
    """
    Validate and return (start_char, end_char) from a raw fact dict.

    Returns (None, None) with a warning logged on any of these conditions:
      - Either field is missing or not an integer
      - start_char < 0 or end_char > len(text)
      - end_char <= start_char  (empty or inverted span)
    """
    start = raw_fact.get("start_char")
    end = raw_fact.get("end_char")

    if not isinstance(start, int) or not isinstance(end, int):
        logger.warning(
            "Fact missing or non-integer span fields — point=%r start=%r end=%r",
            raw_fact.get("point", "")[:60],
            start,
            end,
        )
        return None, None

    text_len = len(text)
    if start < 0 or end > text_len or end <= start:
        logger.warning(
            "Fact has out-of-bounds or inverted span — point=%r start=%d end=%d text_len=%d",
            raw_fact.get("point", "")[:60],
            start,
            end,
            text_len,
        )
        return None, None

    return start, end


def extract_atomic_facts(
    model: "LLMCompletion",
    system_prompt: str,
    user_prompt_template: str,
    text: str,
    path_id: str,
    section_id: str,
) -> list[AtomicFact]:
    """Execute the extraction pipeline for a specific section."""
    user_message = user_prompt_template.format(text=text, path_id=path_id)
    response = model.completion(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        response_format=list[Dict[str, Any]],
        temperature=0.0,
    )

    if not response.formatted_response:
        return []

    raw_facts = response.formatted_response
    if not isinstance(raw_facts, list):
        logger.error("Expected list from LLM, got %s", type(raw_facts))
        return []

    complete_facts = []
    for raw_fact in raw_facts:
        start_char, end_char = _validate_span(raw_fact, text)

        fact = AtomicFact(
            section_id=section_id,
            path_id=path_id,
            point=raw_fact.get("point", ""),
            questions=raw_fact.get("questions", []),
            rank=raw_fact.get("rank"),
            reason=raw_fact.get("reason", ""),
            start_char=start_char,
            end_char=end_char,
        )
        complete_facts.append(fact)

    return complete_facts

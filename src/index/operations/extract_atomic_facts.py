# src/index/operations/extract_atomic_facts.py
from typing import TYPE_CHECKING, Any, Dict

from src.core.atomic_fact import AtomicFact
from src.core.enums import Tier

if TYPE_CHECKING:
    from src.infrastructure.llm.completion import LLMCompletion

import logging

logger = logging.getLogger(__name__)


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
        logger.error(f"Expected list from LLM, got {type(raw_facts)}")
        return []

    complete_facts = []

    for raw_fact in raw_facts:
        fact = AtomicFact(
            section_id=section_id,
            path_id=path_id,
            point=raw_fact.get("point", ""),
            rank=raw_fact.get("rank"),
            reason=raw_fact.get("reason", ""),
        )
        complete_facts.append(fact)

    return complete_facts

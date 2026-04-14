# src/index/operations/extract_atomic_facts.py
from typing import TYPE_CHECKING

from src.core.atomic_fact import AtomicFact

if TYPE_CHECKING:
    from src.infrastructure.llm.completion import LLMCompletion


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
            {"role": "user", "content": user_prompt_template},
        ],
        response_format=list[AtomicFact],
        temperature=0.0,
    )

    if not response.formatted_response:
        return []

    facts = response.formatted_response
    for fact in facts:
        fact.section_id = section_id
        fact.path_id = path_id

    return facts

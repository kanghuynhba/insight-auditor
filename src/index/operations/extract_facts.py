# src/index/operations/extract_facts.py
from typing import Any, Dict, List

from src.core.atomic_fact import AtomicFact
from src.core.text_chunk import TextChunk
from src.infrastructure.llm.completion.completion import LLMCompletion


async def extract_facts(
    chunk: TextChunk,
    llm: "LLMCompletion",
    system_prompt: str,
    user_prompt_template: str,
) -> List[AtomicFact]:
    """Operation to extract structured atomic facts from a text chunk."""
    user_message = user_prompt_template.format(text=chunk.text, path_id=chunk.path_id)

    response = await llm.completion(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        response_format=List[Dict[str, Any]],
        temperature=0.0,
    )

    if not response.formatted_response:
        return []

    facts = []
    for raw in response.formatted_response:
        facts.append(
            AtomicFact(
                section_id=chunk.section_id,
                chunk_id=chunk.id,
                path_id=chunk.path_id,
                point=raw.get("point", ""),
                questions=raw.get("questions", []),
                rank=raw.get("rank"),
                reason=raw.get("reason", ""),
                # Offsets relative to the chunk text
                start_char=raw.get("start_char"),
                end_char=raw.get("end_char"),
            )
        )
    return facts

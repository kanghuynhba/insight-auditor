"""LLM fact response parsing and fact construction."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Protocol

from src.domain import AtomicFact, TextChunk, count_tokens

logger = logging.getLogger(__name__)


class CompletionClient(Protocol):
    async def async_completion(self, **kwargs: Any) -> Any: ...


def parse_fact_payload(raw_data: object) -> list[dict[str, Any]]:
    """Return the fact list from the only supported LLM fact payload shapes."""
    if isinstance(raw_data, str):
        raw_data = json.loads(raw_data)

    if isinstance(raw_data, list):
        facts = raw_data
    elif isinstance(raw_data, dict) and isinstance(raw_data.get("facts"), list):
        facts = raw_data["facts"]
    else:
        raise ValueError("LLM fact response must be a list or {'facts': [...]}")

    invalid = next((item for item in facts if not isinstance(item, dict)), None)
    if invalid is not None:
        raise ValueError(
            f"LLM fact response items must be objects, got {type(invalid).__name__}"
        )

    return facts


async def extract_facts(
    chunk: TextChunk,
    llm: CompletionClient,
    system_prompt: str,
    user_prompt_template: str,
) -> List[AtomicFact]:
    """Extract structured atomic facts from a text chunk."""
    token_count = count_tokens(chunk.text)
    max_facts = min(8, max(3, token_count // 150))

    lines = chunk.text.split("\n", 1)
    body_text = lines[1] if len(lines) > 1 else chunk.text

    user_message = user_prompt_template.format(
        body_text=body_text,
        max_facts=max_facts,
        chunk_token_count=token_count,
    )

    response = await llm.async_completion(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        response_format=List[Dict[str, Any]],
    )

    raw_data = parse_fact_payload(response.formatted_response)

    facts = []
    for raw in raw_data:
        if raw.get("from_overlap") is True:
            continue

        global_start = _offset(chunk.start_char, raw.get("start_char"))
        global_end = _offset(chunk.start_char, raw.get("end_char"))

        try:
            facts.append(
                AtomicFact(
                    section_id=chunk.section_id,
                    chunk_id=chunk.id,
                    point=raw["point"],
                    questions=raw.get("questions", []),
                    rank=raw.get("rank"),
                    reason=raw.get("reason", ""),
                    start_char=global_start,
                    end_char=global_end,
                )
            )
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("Skipping malformed fact from chunk %s: %s", chunk.id[:8], exc)

    return facts


def _offset(base: int, value: object) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int):
        raise ValueError(f"character span must be an integer, got {type(value).__name__}")
    return base + value

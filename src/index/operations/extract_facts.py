import json
import logging
from typing import Any, Dict, List

from src.core.atomic_fact import AtomicFact
from src.core.text_chunk import TextChunk
from src.infrastructure.llm.completion.completion import LLMCompletion
from tiktoken import get_encoding

logger = logging.getLogger(__name__)


async def extract_facts(
    chunk: TextChunk,
    llm: "LLMCompletion",
    system_prompt: str,
    user_prompt_template: str,
) -> List[AtomicFact]:
    """Extract structured atomic facts from a text chunk."""

    # 1. Token count
    _enc = get_encoding("cl100k_base")
    token_count = len(_enc.encode(chunk.text))
    max_facts = min(8, max(3, token_count // 150))

    # 2. Strip breadcrumb header
    lines = chunk.text.split("\n", 1)
    body_text = lines[1] if len(lines) > 1 else chunk.text

    # 3. Prepare user message
    user_message = user_prompt_template.format(
        body_text=body_text,
        max_facts=max_facts,
        chunk_token_count=token_count,
    )

    # 4. Call LLM
    response = await llm.async_completion(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        response_format=List[Dict[str, Any]],
    )

    # 5. Parse response – handle string, list, or dict
    raw_data = response.formatted_response
    if isinstance(raw_data, str):
        try:
            raw_data = json.loads(raw_data)
        except json.JSONDecodeError:
            logger.error(f"LLM returned non‑JSON string: {raw_data[:200]}")
            return []

    # If it's a dict, try to extract the list from common keys
    if isinstance(raw_data, dict):
        # Look for typical keys that might contain the fact list
        list_candidate = None
        for key in ["facts", "result", "data", "items", "atomic_facts"]:
            if key in raw_data and isinstance(raw_data[key], list):
                list_candidate = raw_data[key]
                break
        if list_candidate is not None:
            raw_data = list_candidate
        else:
            # If no list found, maybe the dict itself is a single fact? Wrap it.
            # But better to log and return empty.
            logger.error(f"Dict response has no list of facts: {raw_data.keys()}")
            return []

    if not isinstance(raw_data, list):
        logger.error(f"Unexpected response type: {type(raw_data)}")
        return []

    # 6. Build facts
    facts = []
    for raw in raw_data:
        if not isinstance(raw, dict):
            logger.warning(f"Skipping non‑dict item: {raw}")
            continue

        # Skip overlap facts
        if raw.get("from_overlap") is True:
            continue

        # Re‑base spans
        raw_start = raw.get("start_char")
        raw_end = raw.get("end_char")
        global_start = (chunk.start_char + raw_start) if raw_start is not None else None
        global_end = (chunk.start_char + raw_end) if raw_end is not None else None

        try:
            facts.append(
                AtomicFact(
                    section_id=chunk.section_id,
                    chunk_id=chunk.id,  # keep if required, or set to None
                    point=raw.get("point", ""),
                    questions=raw.get("questions", []),
                    rank=raw.get("rank"),
                    reason=raw.get("reason", ""),
                    start_char=global_start,
                    end_char=global_end,
                )
            )
        except Exception as e:
            logger.warning(f"Skipping malformed fact from chunk {chunk.id[:8]}: {e}")

    return facts

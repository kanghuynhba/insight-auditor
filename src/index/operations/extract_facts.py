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
    """Operation to extract structured atomic facts from a text chunk."""

    # 1. Compute accurate token count using tiktoken (matches NaturalBoundaryChunker)
    _enc = get_encoding("cl100k_base")
    token_count = len(_enc.encode(chunk.text))

    # 2. Dynamic fact budget: prevents "dilution" in small chunks
    max_facts = min(8, max(3, token_count // 150))

    # 3. Strip the breadcrumb header prepended by the chunker
    # chunk.text = "[Book > Chapter > Section]\n{body}"
    lines = chunk.text.split("\n", 1)
    body_text = lines[1] if len(lines) > 1 else chunk.text

    # 4. Prepare user message with specific instruction variables
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

    if not response.formatted_response:
        return []

    facts = []
    for raw in response.formatted_response:
        # 5. Filter overlap facts in Python (don't save to DB)
        if raw.get("from_overlap") is True:
            continue

        # 6. Re-base local spans to global section spans
        # The LLM's start_char is relative to body_text[0].
        # chunk.start_char is the offset of body_text[0] in the section's text.
        raw_start = raw.get("start_char")
        raw_end = raw.get("end_char")

        global_start = (chunk.start_char + raw_start) if raw_start is not None else None
        global_end = (chunk.start_char + raw_end) if raw_end is not None else None

        try:
            facts.append(
                AtomicFact(
                    section_id=chunk.section_id,
                    chunk_id=chunk.id,
                    point=raw.get("point", ""),
                    questions=raw.get("questions", []),
                    rank=raw.get("rank"),
                    reason=raw.get("reason", ""),
                    start_char=global_start,
                    end_char=global_end,
                )
            )
        except Exception as e:
            # Catches validation errors (e.g., end_char <= start_char)
            logger.warning(f"Skipping malformed fact from chunk {chunk.id[:8]}: {e}")

    return facts

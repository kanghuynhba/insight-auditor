import logging
import re
from functools import lru_cache

import tiktoken

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _encoder():
    try:
        return tiktoken.get_encoding("cl100k_base")
    except Exception as exc:
        logger.warning(
            "Falling back to approximate token counting; tiktoken encoder unavailable: %s",
            exc,
        )
        return None


def count_tokens(text: str) -> int:
    encoder = _encoder()
    if encoder is not None:
        return max(1, len(encoder.encode(text)))

    tokens = re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE)
    return max(1, len(tokens))

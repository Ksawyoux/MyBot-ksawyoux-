"""
src/utils/tokens.py — Token counting utilities
"""

import re
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Try to use tiktoken; fall back to a word-count approximation
try:
    import tiktoken
    _enc = tiktoken.get_encoding("cl100k_base")
    _USE_TIKTOKEN = True
except ImportError:
    _enc = None
    _USE_TIKTOKEN = False
    logger.warning("tiktoken not available — using word-count token estimator")


def count_tokens(text: str) -> int:
    """Return an estimated token count for the given text."""
    if _USE_TIKTOKEN and _enc:
        return len(_enc.encode(text))
    # Simple approximation: ~0.75 words per token → 1 token ≈ 4 chars
    return max(1, len(text) // 4)


def count_messages_tokens(messages: list[dict]) -> int:
    """Total token count across a list of {role, content} dicts."""
    return sum(count_tokens(m.get("content", "")) for m in messages)

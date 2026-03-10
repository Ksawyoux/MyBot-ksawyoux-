"""
src/memory/short_term.py — Retrieve recent conversation history from DB
Monitors token count and triggers summarization when over threshold.
"""

from src.config.settings import TOKEN_THRESHOLD
from src.db.conversations import get_recent_messages
from src.utils.tokens import count_messages_tokens
from src.utils.logging import get_logger

logger = get_logger(__name__)


def get_short_term_context(session_id: str, limit: int = 30) -> tuple[list[dict], bool]:
    """
    Fetch recent messages for the session.
    Returns (messages, needs_summarization).
    needs_summarization is True when total tokens exceed TOKEN_THRESHOLD.
    """
    messages = get_recent_messages(session_id, limit=limit)
    total_tokens = count_messages_tokens(messages)

    needs_summarization = total_tokens > TOKEN_THRESHOLD
    if needs_summarization:
        logger.info(
            "Session %s context at %d tokens (threshold=%d) — summarization needed",
            session_id[:8], total_tokens, TOKEN_THRESHOLD,
        )

    return messages, needs_summarization

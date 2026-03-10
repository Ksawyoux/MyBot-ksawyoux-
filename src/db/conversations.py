"""
src/db/conversations.py — Conversation storage CRUD
"""

from datetime import datetime
from sqlalchemy import text
from src.db.connection import get_db
from src.utils.logging import get_logger

logger = get_logger(__name__)


def save_message(session_id: str, role: str, content: str, tokens: int = 0) -> int:
    """Persist a message to the conversations table. Returns the new row id."""
    try:
        with get_db() as db:
            row = db.execute(
                text(
                    "INSERT INTO conversations (session_id, role, content, tokens) "
                    "VALUES (:sid, :role, :content, :tokens) RETURNING id"
                ),
                {"sid": session_id, "role": role, "content": content, "tokens": tokens},
            ).fetchone()
            return row[0] if row else -1
    except Exception as exc:
        logger.error("Failed to save message: %s", exc)
        return -1


def get_recent_messages(session_id: str, limit: int = 20) -> list[dict]:
    """Return recent non-summarized messages for the session, oldest first."""
    try:
        with get_db() as db:
            rows = db.execute(
                text(
                    "SELECT role, content, tokens FROM conversations "
                    "WHERE session_id = :sid AND summarized = FALSE "
                    "ORDER BY timestamp DESC LIMIT :lim"
                ),
                {"sid": session_id, "lim": limit},
            ).fetchall()
            # Reverse so oldest is first
            return [{"role": r[0], "content": r[1], "tokens": r[2]} for r in reversed(rows)]
    except Exception as exc:
        logger.error("Failed to get messages: %s", exc)
        return []


def get_conversation_stats() -> dict:
    """Stats for /status command."""
    try:
        with get_db() as db:
            row = db.execute(
                text("SELECT COUNT(*), COALESCE(SUM(tokens), 0) FROM conversations")
            ).fetchone()
            return {"total_messages": row[0] or 0, "total_tokens": row[1] or 0}
    except Exception:
        return {}

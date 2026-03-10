"""
src/db/conversations.py — Conversation storage CRUD
"""

from datetime import datetime
from src.db.connection import get_db
from src.db.models import Conversation
from src.utils.logging import get_logger
from sqlalchemy import func

logger = get_logger(__name__)


def save_message(session_id: str, role: str, content: str, tokens: int = 0) -> int:
    """Persist a message to the conversations table. Returns the new row id."""
    try:
        with get_db() as db:
            msg = Conversation(session_id=session_id, role=role, content=content, tokens=tokens)
            db.add(msg)
            db.commit()
            db.refresh(msg)
            return msg.id
    except Exception as exc:
        logger.error("Failed to save message: %s", exc)
        return -1


def get_recent_messages(session_id: str, limit: int = 20) -> list[dict]:
    """Return recent non-summarized messages for the session, oldest first."""
    try:
        with get_db() as db:
            msgs = db.query(Conversation).filter(
                Conversation.session_id == session_id,
                Conversation.summarized == False
            ).order_by(Conversation.timestamp.desc()).limit(limit).all()
            
            # Reverse so oldest is first
            return [{"role": m.role, "content": m.content, "tokens": m.tokens} for m in reversed(msgs)]
    except Exception as exc:
        logger.error("Failed to get messages: %s", exc)
        return []


def get_conversation_stats() -> dict:
    """Stats for /status command."""
    try:
        with get_db() as db:
            total_msgs = db.query(func.count(Conversation.id)).scalar() or 0
            total_tokens = db.query(func.sum(Conversation.tokens)).scalar() or 0
            return {"total_messages": total_msgs, "total_tokens": int(total_tokens)}
    except Exception:
        return {}

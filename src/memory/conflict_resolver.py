"""
src/memory/conflict_resolver.py — Detect conflicting facts
Currently just flags them; full user-interactive resolution is Phase 5 (Approval).
"""

from typing import Optional
from sqlalchemy import text
from src.db.connection import get_db
from src.utils.logging import get_logger

logger = get_logger(__name__)


def find_conflicting_fact(category: str, key: str) -> Optional[dict]:
    """Look for an existing active fact with the same category and key."""
    try:
        with get_db() as db:
            row = db.execute(
                text(
                    "SELECT id, value, created_at FROM facts "
                    "WHERE category = :cat AND key = :key AND superseded_by IS NULL"
                ),
                {"cat": category, "key": key},
            ).fetchone()

            if row:
                return {"id": row[0], "value": row[1], "created_at": str(row[2])}
            return None
    except Exception as exc:
        logger.error("Failed to check for conflicting facts: %s", exc)
        return None


def resolve_conflict(old_fact_id: int, new_fact_id: int) -> bool:
    """Mark the old fact as superseded by the new one."""
    try:
        with get_db() as db:
            db.execute(
                text("UPDATE facts SET superseded_by = :new_id WHERE id = :old_id"),
                {"new_id": new_fact_id, "old_id": old_fact_id},
            )
            logger.info("Fact %d superseded by %d", old_fact_id, new_fact_id)
            return True
    except Exception as exc:
        logger.error("Failed to resolve conflict: %s", exc)
        return False

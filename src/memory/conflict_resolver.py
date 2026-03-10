"""
src/memory/conflict_resolver.py — Detect conflicting facts
Currently just flags them; full user-interactive resolution is Phase 5 (Approval).
"""

from typing import Optional
from src.db.connection import get_db
from src.db.models import Fact
from src.utils.logging import get_logger

logger = get_logger(__name__)


def find_conflicting_fact(category: str, key: str) -> Optional[dict]:
    """Look for an existing active fact with the same category and key."""
    try:
        with get_db() as db:
            fact = db.query(Fact).filter(
                Fact.category == category,
                Fact.key == key,
                Fact.superseded_by == None
            ).first()

            if fact:
                return {"id": fact.id, "value": fact.value, "created_at": str(fact.created_at)}
            return None
    except Exception as exc:
        logger.error("Failed to check for conflicting facts: %s", exc)
        return None


def resolve_conflict(old_fact_id: int, new_fact_id: int) -> bool:
    """Mark the old fact as superseded by the new one."""
    try:
        with get_db() as db:
            fact = db.query(Fact).filter(Fact.id == old_fact_id).first()
            if fact:
                fact.superseded_by = new_fact_id
                db.commit()
                logger.info("Fact %d superseded by %d", old_fact_id, new_fact_id)
                return True
            return False
    except Exception as exc:
        logger.error("Failed to resolve conflict: %s", exc)
        return False

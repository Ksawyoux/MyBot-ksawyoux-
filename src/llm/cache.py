"""
src/llm/cache.py — LLM response caching backed by Supabase cache table
"""

import hashlib
import json
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import text
from src.db.connection import get_db
from src.utils.logging import get_logger

logger = get_logger(__name__)

CACHE_TTL_HOURS = 24  # Default TTL for cached responses


def _hash_messages(messages: list[dict], model: str) -> str:
    """Deterministic hash for (messages, model) pair."""
    payload = json.dumps({"messages": messages, "model": model}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def get_cached_response(messages: list[dict], model: str) -> Optional[str]:
    """Return cached response if it exists and has not expired."""
    key = _hash_messages(messages, model)
    try:
        with get_db() as db:
            row = db.execute(
                text(
                    "SELECT response FROM cache "
                    "WHERE prompt_hash = :h AND (expires_at IS NULL OR expires_at > NOW())"
                ),
                {"h": key},
            ).fetchone()
            if row:
                # Bump hit count
                db.execute(
                    text("UPDATE cache SET hit_count = hit_count + 1, last_hit = NOW() WHERE prompt_hash = :h"),
                    {"h": key},
                )
                logger.debug("Cache HIT for hash %s", key[:8])
                return row[0]
    except Exception as exc:
        logger.warning("Cache lookup failed: %s", exc)
    return None


def store_cached_response(messages: list[dict], model: str, response: str, tokens_saved: int = 0) -> None:
    """Persist a response to cache with TTL."""
    key = _hash_messages(messages, model)
    expires = datetime.utcnow() + timedelta(hours=CACHE_TTL_HOURS)
    
    # Extract a preview from the last user message
    preview = "..."
    for msg in reversed(messages):
        if msg.get("role") == "user":
            preview = msg.get("content", "")[:120].replace("\n", " ")
            break
            
    try:
        with get_db() as db:
            db.execute(
                text(
                    "INSERT INTO cache (prompt_hash, prompt_preview, response, model_used, tokens_saved, expires_at) "
                    "VALUES (:h, :preview, :resp, :model, :tokens, :exp) "
                    "ON CONFLICT (prompt_hash) DO UPDATE "
                    "SET response = EXCLUDED.response, expires_at = EXCLUDED.expires_at, last_hit = NOW()"
                ),
                {
                    "h": key,
                    "preview": preview,
                    "resp": response,
                    "model": model,
                    "tokens": tokens_saved,
                    "exp": expires,
                },
            )
        logger.debug("Cache STORE for hash %s", key[:8])
    except Exception as exc:
        logger.warning("Cache store failed: %s", exc)


def get_cache_stats() -> dict:
    """Return cache statistics for /status command."""
    try:
        with get_db() as db:
            row = db.execute(
                text("SELECT COUNT(*), COALESCE(SUM(hit_count), 0), COALESCE(SUM(tokens_saved), 0) FROM cache")
            ).fetchone()
            return {
                "entries": row[0] or 0,
                "total_hits": row[1] or 0,
                "tokens_saved": row[2] or 0,
            }
    except Exception as exc:
        logger.warning("Cache stats query failed: %s", exc)
        return {}

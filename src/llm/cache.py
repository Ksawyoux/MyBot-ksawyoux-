"""
src/llm/cache.py — LLM response caching backed by Supabase cache table
"""

import hashlib
import json
from datetime import datetime, timedelta
from typing import Optional

from src.db.connection import get_db
from src.db.models import Cache
from src.utils.logging import get_logger
from sqlalchemy import func

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
            now = datetime.utcnow()
            cache_entry = db.query(Cache).filter(
                Cache.prompt_hash == key,
                (Cache.expires_at == None) | (Cache.expires_at > now)
            ).first()
            
            if cache_entry:
                # Bump hit count
                cache_entry.hit_count += 1
                cache_entry.last_hit = func.now()
                db.commit()
                logger.debug("Cache HIT for hash %s", key[:8])
                return cache_entry.response
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
            
    if not response:
        logger.warning("Attempted to store empty response for hash %s. Skipping.", key[:8])
        return

    try:
        with get_db() as db:
            # Upsert using query and update/insert
            cache_entry = db.query(Cache).filter(Cache.prompt_hash == key).first()
            if cache_entry:
                cache_entry.response = response
                cache_entry.expires_at = expires
                cache_entry.last_hit = func.now()
                cache_entry.prompt_preview = preview
                cache_entry.model_used = model
                cache_entry.tokens_saved = tokens_saved
            else:
                cache_entry = Cache(
                    prompt_hash=key,
                    prompt_preview=preview,
                    response=response,
                    model_used=model,
                    tokens_saved=tokens_saved,
                    expires_at=expires
                )
                db.add(cache_entry)
            db.commit()
        logger.debug("Cache STORE for hash %s", key[:8])
    except Exception as exc:
        logger.warning("Cache store failed: %s", exc)


def get_cache_stats() -> dict:
    """Return cache statistics for /status command."""
    try:
        with get_db() as db:
            count = db.query(func.count(Cache.id)).scalar() or 0
            hits = db.query(func.sum(Cache.hit_count)).scalar() or 0
            tokens = db.query(func.sum(Cache.tokens_saved)).scalar() or 0
            return {
                "entries": count,
                "total_hits": int(hits),
                "tokens_saved": int(tokens),
            }
    except Exception as exc:
        logger.warning("Cache stats query failed: %s", exc)
        return {}

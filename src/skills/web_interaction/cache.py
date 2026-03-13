"""
src/skills/web_interaction/cache.py — Simple URL-based content cache.
"""

import time
from typing import Optional, Dict, Any
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Simple in-memory cache for Phase 1. 
# In Phase 5+, we could move this to Redis or DB.
_cache: Dict[str, Dict[str, Any]] = {}

DEFAULT_TTL = 3600  # 1 hour

def get_from_cache(url: str) -> Optional[Any]:
    """Retrieves content from cache if it exists and hasn't expired."""
    entry = _cache.get(url)
    if entry:
        if time.time() < entry["expires_at"]:
            logger.debug("Cache hit for URL: %s", url)
            return entry["data"]
        else:
            logger.debug("Cache expired for URL: %s", url)
            del _cache[url]
    return None

def set_in_cache(url: str, data: Any, ttl: int = DEFAULT_TTL) -> None:
    """Stores content in cache with a TTL."""
    _cache[url] = {
        "data": data,
        "expires_at": time.time() + ttl
    }
    logger.debug("Cached URL: %s (TTL: %d)", url, ttl)

def clear_cache() -> None:
    """Clears the entire cache."""
    _cache.clear()
    logger.info("Web cache cleared.")

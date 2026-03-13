import time
import hashlib
from typing import Any, Dict, Optional
from collections import OrderedDict

class WebCache:
    def __init__(self, max_size: int = 100):
        self.cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self.max_size = max_size

    def _get_key(self, prefix: str, query: str) -> str:
        return hashlib.md5(f"{prefix}:{query}".encode()).hexdigest()

    def get(self, prefix: str, query: str) -> Optional[Any]:
        key = self._get_key(prefix, query)
        if key in self.cache:
            item = self.cache[key]
            if time.time() < item["expiry"]:
                # Move to end (LRU)
                self.cache.move_to_end(key)
                return item["data"]
            else:
                del self.cache[key]
        return None

    def set(self, prefix: str, query: str, data: Any, ttl_seconds: int):
        key = self._get_key(prefix, query)
        if len(self.cache) >= self.max_size:
            # Pop oldest
            self.cache.popitem(last=False)
        
        self.cache[key] = {
            "data": data,
            "expiry": time.time() + ttl_seconds
        }
        self.cache.move_to_end(key)

# Singleton
web_cache = WebCache()

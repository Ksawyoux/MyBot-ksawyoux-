"""
src/llm/rate_limiter.py — Token bucket rate limiter
Enforces per-minute and per-hour request limits.
"""

import time
import asyncio
from collections import deque
from src.config.models import RATE_LIMITS
from src.utils.logging import get_logger

logger = get_logger(__name__)


class RateLimiter:
    """
    Token bucket implementation enforcing:
    - Max N requests per minute
    - Max M requests per hour
    - Cooldown on receiving a 429 response
    """

    def __init__(self) -> None:
        self.rpm = RATE_LIMITS["requests_per_minute"]
        self.rph = RATE_LIMITS["requests_per_hour"]
        self.cooldown_seconds = RATE_LIMITS["cooldown_on_429"]

        self._minute_window: deque[float] = deque()
        self._hour_window: deque[float] = deque()
        self._cooldown_until: float = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Block until a request slot is available."""
        async with self._lock:
            while True:
                now = time.monotonic()

                # Cooldown from a 429
                if now < self._cooldown_until:
                    wait = self._cooldown_until - now
                    logger.warning("Rate limiter cooldown — waiting %.1fs", wait)
                    await asyncio.sleep(wait)
                    continue

                # Evict timestamps outside windows
                cutoff_min = now - 60
                cutoff_hr = now - 3600
                while self._minute_window and self._minute_window[0] < cutoff_min:
                    self._minute_window.popleft()
                while self._hour_window and self._hour_window[0] < cutoff_hr:
                    self._hour_window.popleft()

                if len(self._minute_window) < self.rpm and len(self._hour_window) < self.rph:
                    self._minute_window.append(now)
                    self._hour_window.append(now)
                    return

                # Calculate wait time
                wait = 0.0
                if len(self._minute_window) >= self.rpm:
                    wait = max(wait, self._minute_window[0] + 60 - now)
                if len(self._hour_window) >= self.rph:
                    wait = max(wait, self._hour_window[0] + 3600 - now)

                logger.debug("Rate limit reached — waiting %.1fs", wait)
                await asyncio.sleep(wait)

    def trigger_cooldown(self) -> None:
        """Call when a 429 is received from the API."""
        self._cooldown_until = time.monotonic() + self.cooldown_seconds
        logger.warning("429 received — cooling down for %ds", self.cooldown_seconds)


# Module-level singleton
_rate_limiter = RateLimiter()


def get_rate_limiter() -> RateLimiter:
    return _rate_limiter

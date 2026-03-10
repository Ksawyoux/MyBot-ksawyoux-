"""
src/memory/working_memory.py — In-memory context for the current session
Sessions expire after 30 minutes of inactivity.
"""

import time
from collections import defaultdict
from typing import Optional
from src.utils.logging import get_logger

logger = get_logger(__name__)

SESSION_TIMEOUT = 1800  # 30 minutes


class WorkingMemory:
    """
    Holds conversation messages for active sessions in memory.
    Messages are automatically flushed when session expires.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, list[dict]] = defaultdict(list)
        self._last_active: dict[str, float] = {}

    def add_message(self, session_id: str, role: str, content: str) -> None:
        self._sessions[session_id].append({"role": role, "content": content})
        self._last_active[session_id] = time.time()

    def get_messages(self, session_id: str) -> list[dict]:
        self._cleanup()
        if self._is_expired(session_id):
            self.clear_session(session_id)
            return []
        return list(self._sessions[session_id])

    def _cleanup(self) -> None:
        """Periodically scan and remove expired sessions to prevent memory leaks."""
        # Only run cleanup occasionally to avoid overhead on every call.
        # A simple modulo check based on the current time in seconds isn't perfect,
        # but randomly running roughly every ~100 calls is fine, or better:
        # just iterate and find expired ones since there shouldn't be too many active ones.
        now = time.time()
        expired_sids = [
            sid for sid, last_active in self._last_active.items()
            if (now - last_active) > SESSION_TIMEOUT
        ]
        for sid in expired_sids:
            self.clear_session(sid)

    def clear_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
        self._last_active.pop(session_id, None)

    def _is_expired(self, session_id: str) -> bool:
        last = self._last_active.get(session_id, 0)
        return (time.time() - last) > SESSION_TIMEOUT

    def session_count(self) -> int:
        return len(self._sessions)


# Module-level singleton
_working_memory = WorkingMemory()


def get_working_memory() -> WorkingMemory:
    return _working_memory

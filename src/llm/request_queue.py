"""
src/llm/request_queue.py — Priority queue for LLM requests (P0–P3)

Priority levels:
  P0 — Interactive (user is waiting)
  P1 — Approval responses
  P2 — Background tasks
  P3 — Scheduled / low priority
"""

import asyncio
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine
from src.utils.logging import get_logger

logger = get_logger(__name__)

PRIORITY_INTERACTIVE = 0
PRIORITY_APPROVAL = 1
PRIORITY_BACKGROUND = 2
PRIORITY_SCHEDULED = 3


@dataclass(order=True)
class QueueItem:
    priority: int
    seq: int  # tiebreaker — lower seq = earlier submitted
    task_fn: Callable[..., Coroutine[Any, Any, Any]] = field(compare=False)
    args: tuple = field(default_factory=tuple, compare=False)
    kwargs: dict = field(default_factory=dict, compare=False)
    future: asyncio.Future = field(default=None, compare=False)


class LLMRequestQueue:
    """
    Async priority queue that processes LLM requests in order P0 → P3.
    Runs in a background task; callers `await` their future to get results.
    """

    def __init__(self) -> None:
        self._queue: asyncio.PriorityQueue[QueueItem] = None
        self._seq = 0
        self._running = False
        self._worker_task: asyncio.Task = None

    async def enqueue(
        self,
        task_fn: Callable[..., Coroutine],
        *args,
        priority: int = PRIORITY_BACKGROUND,
        **kwargs,
    ) -> Any:
        """Submit a coroutine to the queue; await the result."""
        loop = asyncio.get_event_loop()
        future: asyncio.Future = loop.create_future()
        self._seq += 1
        item = QueueItem(
            priority=priority,
            seq=self._seq,
            task_fn=task_fn,
            args=args,
            kwargs=kwargs,
            future=future,
        )
        await self._queue.put(item)
        logger.debug("Enqueued task P%d seq=%d", priority, self._seq)
        return await future

    async def _worker(self) -> None:
        """Continuous worker loop — processes items from the priority queue."""
        self._running = True
        logger.info("LLM request queue worker started.")
        while True:
            item = await self._queue.get()
            try:
                result = await item.task_fn(*item.args, **item.kwargs)
                if not item.future.done():
                    item.future.set_result(result)
            except Exception as exc:
                if not item.future.done():
                    item.future.set_exception(exc)
            finally:
                self._queue.task_done()

    def start(self, loop: asyncio.AbstractEventLoop = None) -> None:
        """Start the worker as a background task."""
        if loop is None:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
        
        if self._queue is None:
            self._queue = asyncio.PriorityQueue()
        self._worker_task = loop.create_task(self._worker())

    def stop(self) -> None:
        """Stop the background worker."""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            logger.info("LLM request queue worker stopped.")

    def qsize(self) -> int:
        return self._queue.qsize()


# Module-level singleton
_queue: LLMRequestQueue = LLMRequestQueue()


def get_request_queue() -> LLMRequestQueue:
    return _queue

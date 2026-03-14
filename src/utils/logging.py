"""
src/utils/logging.py — Structured logger with LOG_LEVEL support and lightweight tracing.

Usage:
    from src.utils.logging import get_logger, trace
    logger = get_logger(__name__)

    async with trace("llm.complete", model="gpt-4o-mini"):
        result = await complete(...)

    # Read current metrics
    from src.utils.logging import get_metrics
    stats = get_metrics()  # {"llm.complete": {"count": 5, "errors": 0, "total_ms": 1234}}
"""

import logging
import sys
import os
import time
from contextlib import asynccontextmanager
from collections import defaultdict
from typing import Any

# Thread-safe in CPython due to the GIL; sufficient for single-process bot
_metrics: dict[str, dict[str, Any]] = defaultdict(lambda: {"count": 0, "errors": 0, "total_ms": 0.0})


@asynccontextmanager
async def trace(operation: str, **tags):
    """
    Async context manager that times an operation and records it in _metrics.
    Logs at DEBUG on success, WARNING on error.
    """
    _log = logging.getLogger("trace")
    start = time.monotonic()
    try:
        yield
        elapsed_ms = (time.monotonic() - start) * 1000
        _metrics[operation]["count"] += 1
        _metrics[operation]["total_ms"] += elapsed_ms
        tag_str = " ".join(f"{k}={v}" for k, v in tags.items())
        _log.debug("TRACE %-40s %6.1f ms  %s", operation, elapsed_ms, tag_str)
    except Exception as exc:
        elapsed_ms = (time.monotonic() - start) * 1000
        _metrics[operation]["count"] += 1
        _metrics[operation]["errors"] += 1
        _metrics[operation]["total_ms"] += elapsed_ms
        _log.warning("TRACE %-40s %6.1f ms  ERROR: %s", operation, elapsed_ms, exc)
        raise


def get_metrics() -> dict:
    """Return a snapshot of all recorded operation metrics."""
    return {
        op: {
            "count": v["count"],
            "errors": v["errors"],
            "avg_ms": round(v["total_ms"] / v["count"], 1) if v["count"] else 0,
            "total_ms": round(v["total_ms"], 1),
        }
        for op, v in _metrics.items()
    }


def get_logger(name: str) -> logging.Logger:
    """Return a named logger with consistent structured formatting."""
    log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_str, logging.INFO)

    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(log_level)
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(log_level)
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.propagate = False

    return logger

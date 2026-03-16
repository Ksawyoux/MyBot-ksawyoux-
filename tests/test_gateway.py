"""
Unit tests for src/llm/gateway.py — the main LLM entrypoint.

All external I/O is mocked:
  - get_model_router      → predictable model names
  - get_request_queue     → direct function call (no worker loop)
  - get_cached_response   → controlled cache hit / miss
  - store_cached_response → captured for assertions
  - call_with_fallback    → returns a canned (text, model, tokens) tuple
  - trace                 → no-op async context manager
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch, call
from contextlib import asynccontextmanager


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_async_cm_mock():
    """Return a callable mock that behaves as an async context manager."""
    mock = MagicMock()
    mock.return_value.__aenter__ = AsyncMock(return_value=None)
    mock.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def patch_all(monkeypatch, mock_router, mock_request_queue):
    """Patch every external dependency in gateway.py for every test."""
    monkeypatch.setattr("src.llm.gateway.get_model_router", lambda: mock_router)
    monkeypatch.setattr("src.llm.gateway.get_request_queue", lambda: mock_request_queue)
    monkeypatch.setattr("src.llm.gateway.trace", _make_async_cm_mock())
    monkeypatch.setattr(
        "src.llm.gateway.call_with_fallback",
        AsyncMock(return_value=("LLM response text", "gpt-4o-mini", 55)),
    )
    monkeypatch.setattr("src.llm.gateway.get_cached_response", MagicMock(return_value=None))
    monkeypatch.setattr("src.llm.gateway.store_cached_response", MagicMock())


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_complete_returns_correct_shape():
    """Return dict must have all required keys with correct types."""
    from src.llm.gateway import complete

    result = await complete("Hello")

    assert set(result.keys()) == {"response", "model", "tokens", "latency_ms", "cache_hit"}
    assert isinstance(result["response"], str)
    assert isinstance(result["model"], str)
    assert isinstance(result["tokens"], int)
    assert isinstance(result["latency_ms"], int)
    assert isinstance(result["cache_hit"], bool)


@pytest.mark.asyncio
async def test_complete_cache_miss_calls_llm(monkeypatch):
    """On cache miss, call_with_fallback must be invoked."""
    from src.llm.gateway import complete

    mock_fallback = AsyncMock(return_value=("response", "gpt-4o-mini", 10))
    monkeypatch.setattr("src.llm.gateway.call_with_fallback", mock_fallback)

    await complete("What is 2+2?")

    mock_fallback.assert_called_once()


@pytest.mark.asyncio
async def test_complete_cache_hit_skips_llm(monkeypatch):
    """On cache hit, call_with_fallback must NOT be called and cache_hit must be True."""
    from src.llm.gateway import complete

    monkeypatch.setattr(
        "src.llm.gateway.get_cached_response",
        MagicMock(return_value="Cached answer"),
    )
    mock_fallback = AsyncMock(return_value=("should not be called", "model", 0))
    monkeypatch.setattr("src.llm.gateway.call_with_fallback", mock_fallback)

    result = await complete("What is 2+2?")

    mock_fallback.assert_not_called()
    assert result["cache_hit"] is True
    assert result["response"] == "Cached answer"
    assert result["tokens"] == 0


@pytest.mark.asyncio
async def test_complete_stores_cache_on_miss(monkeypatch):
    """After a cache miss, store_cached_response must be called with the response."""
    from src.llm.gateway import complete

    mock_store = MagicMock()
    monkeypatch.setattr("src.llm.gateway.store_cached_response", mock_store)

    await complete("Tell me a joke")

    mock_store.assert_called_once()
    # First positional arg is the messages list; third is the response text
    _messages, _model, stored_response, *_ = mock_store.call_args[0]
    assert stored_response == "LLM response text"


@pytest.mark.asyncio
async def test_complete_skips_cache_for_json_format(monkeypatch):
    """response_format={"type":"json_object"} must bypass cache read and cache write."""
    from src.llm.gateway import complete

    mock_get_cache = MagicMock(return_value=None)
    mock_store = MagicMock()
    monkeypatch.setattr("src.llm.gateway.get_cached_response", mock_get_cache)
    monkeypatch.setattr("src.llm.gateway.store_cached_response", mock_store)

    await complete("Return JSON", response_format={"type": "json_object"})

    mock_get_cache.assert_not_called()
    mock_store.assert_not_called()


@pytest.mark.asyncio
async def test_complete_uses_model_tier(monkeypatch, mock_router):
    """The model tier must be passed to ModelRouter.get_models()."""
    from src.llm.gateway import complete

    await complete("Summarise this", model_tier="capable")

    mock_router.get_models.assert_called_with("capable")


@pytest.mark.asyncio
async def test_complete_passes_priority_to_queue(monkeypatch):
    """The priority argument must be forwarded to queue.enqueue()."""
    from src.llm.gateway import complete
    from src.llm.request_queue import PRIORITY_INTERACTIVE

    captured = {}

    async def capturing_enqueue(fn, *args, priority=2, **kwargs):
        captured["priority"] = priority
        return await fn()

    mock_queue = MagicMock()
    mock_queue.enqueue = capturing_enqueue
    monkeypatch.setattr("src.llm.gateway.get_request_queue", lambda: mock_queue)

    await complete("Urgent query", priority=PRIORITY_INTERACTIVE)

    assert captured["priority"] == PRIORITY_INTERACTIVE

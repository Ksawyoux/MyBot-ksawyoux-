"""
Shared fixtures for the test suite.
Env vars are set at module level so they are present before any src.* imports.
"""
import os

# Required env vars — must be set before any src.* module is imported
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test_bot_token_123")
os.environ.setdefault("TELEGRAM_ADMIN_USER_ID", "0")
os.environ.setdefault("SUPABASE_DB_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("OPENROUTER_API_KEY", "test_openrouter_key")
os.environ.setdefault("OPENAI_API_KEY", "test_openai_key")
os.environ.setdefault("LOG_LEVEL", "WARNING")

import pytest
from contextlib import contextmanager
from unittest.mock import MagicMock, AsyncMock


@pytest.fixture
def db_session():
    """A mock SQLAlchemy DB session that supports common query patterns."""
    session = MagicMock()
    # Support: db.query(Model).filter(...).all() → []
    session.query.return_value.filter.return_value.all.return_value = []
    # Support: db.query(Model).filter(...).first() → None
    session.query.return_value.filter.return_value.first.return_value = None
    return session


@pytest.fixture
def mock_get_db(db_session):
    """Returns a context-manager factory that yields the mock db_session."""
    @contextmanager
    def _get_db():
        yield db_session
    return _get_db


@pytest.fixture
def standard_llm_response():
    """Standard successful LLM response dict as returned by gateway.complete()."""
    return {
        "response": "This is a test response.",
        "model": "gpt-4o-mini",
        "tokens": 42,
        "latency_ms": 100,
        "cache_hit": False,
    }


@pytest.fixture
def mock_router():
    """Mock ModelRouter returning predictable model names."""
    router = MagicMock()
    router.get_models.return_value = ("gpt-4o-mini", "gpt-3.5-turbo")
    router.get_max_tokens.return_value = 2048
    return router


@pytest.fixture
def mock_request_queue():
    """
    Mock LLMRequestQueue whose enqueue() directly awaits the submitted function.
    This lets us test the _do_complete closure inside gateway.complete() without
    starting a real worker loop.
    """
    queue = MagicMock()

    async def _enqueue(fn, *args, priority=2, **kwargs):
        return await fn()

    queue.enqueue = _enqueue
    return queue

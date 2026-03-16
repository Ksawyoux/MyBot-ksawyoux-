"""
Unit tests for src/shared/message_processor.py — the core message pipeline.

Every external I/O dependency is mocked so tests run without a real DB,
LLM API, or file system.

Patch targets use the name as it appears in message_processor.py's namespace
(i.e., where it is *used*, not where it is *defined*).
"""

import asyncio
import pytest
import httpx
from contextlib import contextmanager
from unittest.mock import MagicMock, AsyncMock, patch, call


# ── Module-level patch target prefix ─────────────────────────────────────────
MP = "src.shared.message_processor"


# ── Shared mock values ────────────────────────────────────────────────────────

_CLASSIFY_RESULT = {
    "type": "simple",
    "priority": 0,
    "intent": {"tier": "fast", "action": "social", "skill_name": ""},
}

_LLM_RESPONSE = {
    "response": "Sure, I can help!",
    "model": "gpt-4o-mini",
    "tokens": 20,
    "latency_ms": 80,
    "cache_hit": False,
}


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def db_session(db_session):  # inherits from conftest
    """Override: facts query returns empty list (no stored facts)."""
    db_session.query.return_value.filter.return_value.all.return_value = []
    return db_session


@pytest.fixture(autouse=True)
def patch_all_deps(monkeypatch, db_session):
    """
    Patch every external dependency touched by process_message().
    Tests can override individual patches via additional monkeypatch calls.
    """
    @contextmanager
    def mock_get_db():
        yield db_session

    # DB
    monkeypatch.setattr(f"{MP}.get_db", mock_get_db)
    monkeypatch.setattr(f"{MP}.save_message", MagicMock(return_value=1))
    monkeypatch.setattr(f"{MP}.create_task", MagicMock(return_value=42))
    monkeypatch.setattr(f"{MP}.update_task", MagicMock())

    # MCP client
    mock_client = MagicMock()
    mock_client.get_connected_servers.return_value = []
    monkeypatch.setattr(f"{MP}.get_mcp_client", lambda: mock_client)

    # Prompts
    monkeypatch.setattr(f"{MP}.build_system_prompt", MagicMock(return_value="system prompt"))

    # Memory
    monkeypatch.setattr(
        f"{MP}.get_short_term_context",
        MagicMock(return_value=([], False)),
    )
    monkeypatch.setattr(
        f"{MP}.enrich_prompt_with_context",
        AsyncMock(side_effect=lambda text: text),  # returns prompt unchanged
    )
    monkeypatch.setattr(
        f"{MP}.summarize_session",
        AsyncMock(),
    )
    monkeypatch.setattr(
        f"{MP}.extract_and_store_facts",
        AsyncMock(),
    )

    # Routing
    monkeypatch.setattr(
        f"{MP}.classify_task",
        AsyncMock(return_value=_CLASSIFY_RESULT),
    )
    monkeypatch.setattr(
        f"{MP}.route_message",
        AsyncMock(return_value=None),  # no internal route by default
    )
    monkeypatch.setattr(
        f"{MP}.route_by_action",
        AsyncMock(return_value="Routed handler response"),
    )

    # Handler init
    monkeypatch.setattr(f"{MP}.register_core_handlers", MagicMock())

    # Scheduler (imported at module level but only used in a path we don't test here)
    monkeypatch.setattr(f"{MP}.get_scheduler", MagicMock())

    # Background tasks — capture calls without actually scheduling coroutines
    monkeypatch.setattr(f"{MP}.asyncio.create_task", MagicMock())


@pytest.fixture
def processor():
    """A MessageProcessor instance with all deps already mocked by patch_all_deps."""
    from src.shared.message_processor import MessageProcessor
    return MessageProcessor()


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_happy_path_returns_output_envelope(processor):
    """process_message() must return an OutputEnvelope on success."""
    from src.output.core.envelope import OutputEnvelope

    result = await processor.process_message("sess-1", "Hello there")

    assert isinstance(result, OutputEnvelope)


@pytest.mark.asyncio
async def test_saves_user_message(processor, monkeypatch):
    """The user's message must be persisted before any LLM call."""
    mock_save = MagicMock(return_value=1)
    monkeypatch.setattr(f"{MP}.save_message", mock_save)

    await processor.process_message("sess-2", "What time is it?")

    # First call should be user message save
    first_call = mock_save.call_args_list[0]
    assert first_call[0][0] == "sess-2"   # session_id
    assert first_call[0][1] == "user"     # role


@pytest.mark.asyncio
async def test_creates_and_completes_task(processor, monkeypatch):
    """A task record must be created and updated to 'completed' on success."""
    mock_create = MagicMock(return_value=99)
    mock_update = MagicMock()
    monkeypatch.setattr(f"{MP}.create_task", mock_create)
    monkeypatch.setattr(f"{MP}.update_task", mock_update)

    await processor.process_message("sess-3", "Tell me a joke")

    mock_create.assert_called_once()

    # update_task is called at least twice: in_progress + completed
    update_statuses = [c[1]["status"] if c[1] else c[0][1] for c in mock_update.call_args_list]
    assert "in_progress" in update_statuses
    assert "completed" in update_statuses


@pytest.mark.asyncio
async def test_internal_route_bypasses_route_by_action(processor, monkeypatch):
    """When route_message returns a string, route_by_action must not be called."""
    monkeypatch.setattr(f"{MP}.route_message", AsyncMock(return_value="Internal answer"))
    mock_route_by_action = AsyncMock(return_value="should not appear")
    monkeypatch.setattr(f"{MP}.route_by_action", mock_route_by_action)

    result = await processor.process_message("sess-4", "show my tasks")

    mock_route_by_action.assert_not_called()
    # The internal answer should appear in the envelope
    assert "Internal answer" in str(result)


@pytest.mark.asyncio
async def test_action_route_called_when_no_internal_route(processor, monkeypatch):
    """When route_message returns None, route_by_action must be invoked."""
    monkeypatch.setattr(f"{MP}.route_message", AsyncMock(return_value=None))
    mock_route = AsyncMock(return_value="Action result")
    monkeypatch.setattr(f"{MP}.route_by_action", mock_route)

    await processor.process_message("sess-5", "Search for Python news")

    mock_route.assert_called_once()


@pytest.mark.asyncio
async def test_http_status_error_returns_error_envelope(processor, monkeypatch):
    """httpx.HTTPStatusError during routing must produce an error OutputEnvelope."""
    from src.output.core.envelope import OutputEnvelope

    mock_response = MagicMock()
    mock_response.status_code = 429

    monkeypatch.setattr(
        f"{MP}.route_by_action",
        AsyncMock(side_effect=httpx.HTTPStatusError("rate limit", request=MagicMock(), response=mock_response)),
    )

    result = await processor.process_message("sess-6", "Do something")

    assert isinstance(result, OutputEnvelope)
    # The content should mention the error
    result_str = str(result.model_dump())
    assert "Error" in result_str or "error" in result_str or "429" in result_str


@pytest.mark.asyncio
async def test_request_error_returns_error_envelope(processor, monkeypatch):
    """httpx.RequestError must produce an error OutputEnvelope."""
    from src.output.core.envelope import OutputEnvelope

    monkeypatch.setattr(
        f"{MP}.route_by_action",
        AsyncMock(side_effect=httpx.RequestError("connection refused")),
    )

    result = await processor.process_message("sess-7", "Do something else")

    assert isinstance(result, OutputEnvelope)


@pytest.mark.asyncio
async def test_exception_marks_task_failed(processor, monkeypatch):
    """Any unexpected exception must update the task status to 'failed'."""
    mock_update = MagicMock()
    monkeypatch.setattr(f"{MP}.update_task", mock_update)
    monkeypatch.setattr(
        f"{MP}.route_by_action",
        AsyncMock(side_effect=RuntimeError("boom")),
    )

    await processor.process_message("sess-8", "Crash me")

    failed_calls = [
        c for c in mock_update.call_args_list
        if (c[1].get("status") == "failed" or (len(c[0]) > 1 and c[0][1] == "failed"))
    ]
    assert len(failed_calls) >= 1


@pytest.mark.asyncio
async def test_multimodal_content_coerces_task_to_simple(processor, monkeypatch):
    """If content is a list (multimodal), task_type must be coerced to 'simple'."""
    # Provide a complex classification
    monkeypatch.setattr(
        f"{MP}.classify_task",
        AsyncMock(return_value={
            "type": "complex",
            "priority": 1,
            "intent": {"tier": "agentic", "action": "research", "skill_name": ""},
        }),
    )
    mock_create = MagicMock(return_value=1)
    monkeypatch.setattr(f"{MP}.create_task", mock_create)

    multimodal_content = [
        {"type": "text", "text": "What is in this image?"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}},
    ]

    await processor.process_message("sess-9", multimodal_content)

    # create_task should be called with "simple" type
    call_kwargs = mock_create.call_args
    task_type_arg = call_kwargs[0][0] if call_kwargs[0] else call_kwargs[1].get("type")
    assert task_type_arg == "simple"


@pytest.mark.asyncio
async def test_skill_prompt_injected_when_active_skill_provided(processor, monkeypatch, tmp_path):
    """When active_skill is set and SKILL.md exists, it must be included in the prompt."""
    # Create a temporary skill directory structure
    skills_dir = tmp_path / "skills" / "test-skill"
    skills_dir.mkdir(parents=True)
    skill_file = skills_dir / "SKILL.md"
    skill_file.write_text("# Test Skill\nYou are a test skill.\n")

    captured_prompts = []

    def capture_build_system_prompt(**kwargs):
        return "base system prompt"

    monkeypatch.setattr(f"{MP}.build_system_prompt", capture_build_system_prompt)

    # Patch os.path.join inside _get_skill_prompt to return our temp file
    import os as _os
    original_join = _os.path.join

    def patched_join(*args):
        # If it looks like a skill path lookup, redirect to tmp_path
        result = original_join(*args)
        if "skills" in result and "SKILL.md" in result and "test-skill" in result:
            return str(skill_file)
        return result

    monkeypatch.setattr("src.shared.message_processor.os.path.join", patched_join)
    monkeypatch.setattr("src.shared.message_processor.os.path.exists", lambda p: True if str(skill_file) in p else _os.path.exists(p))

    captured_system_prompts = []
    original_route = AsyncMock(return_value="skill response")
    monkeypatch.setattr(f"{MP}.route_by_action", original_route)

    await processor.process_message("sess-10", "Help me with this", active_skill="test-skill")

    # The handler context passed to route_by_action should include the skill content
    call_args = original_route.call_args
    handler_context = call_args[0][2] if len(call_args[0]) >= 3 else call_args[1].get("context", {})
    system_prompt_used = handler_context.get("system_prompt", "")
    assert "test-skill" in system_prompt_used or "Test Skill" in system_prompt_used


@pytest.mark.asyncio
async def test_background_tasks_fired_after_response(processor, monkeypatch):
    """asyncio.create_task must be called for background summarisation and fact extraction."""
    mock_create_task = MagicMock()
    monkeypatch.setattr(f"{MP}.asyncio.create_task", mock_create_task)

    # Trigger summarisation path
    monkeypatch.setattr(
        f"{MP}.get_short_term_context",
        MagicMock(return_value=(
            [{"role": "user", "content": "old msg"}] * 6,
            True,  # needs_summarization = True
        )),
    )

    await processor.process_message("sess-11", "Hello")

    # At least 1 background task must have been scheduled
    assert mock_create_task.call_count >= 1

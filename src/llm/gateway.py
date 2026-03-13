"""
src/llm/gateway.py — Main LLM entrypoint
Single async function that handles: cache → rate limit → queue → model router → fallback chain
"""

import time
from typing import Optional

from src.llm.cache import get_cached_response, store_cached_response
from src.llm.model_router import get_model_router
from src.llm.fallback_chain import call_with_fallback, stream_with_fallback
from src.llm.request_queue import get_request_queue, PRIORITY_BACKGROUND
from src.utils.logging import get_logger

logger = get_logger(__name__)


async def complete(
    prompt: str,
    model_tier: str = "lightweight",
    system_prompt: Optional[str] = None,
    conversation_history: Optional[list[dict]] = None,
    use_cache: bool = True,
    priority: int = PRIORITY_BACKGROUND,
    response_format: Optional[dict] = None,
    metadata: Optional[dict] = None,
) -> dict:
    """
    Single entry point for all LLM calls.
    Uses a priority queue to manage concurrency and rate limits.
    """
    router = get_model_router()
    primary_model, fallback_model = router.get_models(model_tier)
    max_tokens = router.get_max_tokens(model_tier)

    async def _do_complete():
        # ── Build messages list ───────────────────────────────────────────────────
        messages: list[dict] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if conversation_history:
            messages.extend(conversation_history)
        messages.append({"role": "user", "content": prompt})

        # ── Cache check ──────────────────────────────────────────────────────────
        if use_cache and not response_format: # Don't cache JSON-formatted responses for now to avoid mismatch
            cached = get_cached_response(messages, primary_model)
            if cached:
                return {
                    "response": cached,
                    "model": primary_model,
                    "tokens": 0,
                    "latency_ms": 0,
                    "cache_hit": True,
                }

        # ── Call LLM with fallback ────────────────────────────────────────────────
        start = time.monotonic()
        response_text, model_used, tokens = await call_with_fallback(
            messages=messages,
            primary_model=primary_model,
            fallback_model=fallback_model,
            max_tokens=max_tokens,
            response_format=response_format,
            metadata=metadata,
        )
        latency_ms = int((time.monotonic() - start) * 1000)

        logger.info(
            "LLM complete | tier=%s model=%s tokens=%d latency=%dms",
            model_tier, model_used, tokens, latency_ms,
        )

        # ── Store in cache ────────────────────────────────────────────────────────
        if use_cache and not response_format:
            store_cached_response(messages, primary_model, response_text, tokens_saved=tokens)

        return {
            "response": response_text,
            "model": model_used,
            "tokens": tokens,
            "latency_ms": latency_ms,
            "cache_hit": False,
        }

    queue = get_request_queue()
    return await queue.enqueue(_do_complete, priority=priority)


async def stream_complete(
    prompt: str,
    model_tier: str = "lightweight",
    system_prompt: Optional[str] = None,
    conversation_history: Optional[list[dict]] = None,
):
    """
    Like complete(), but yields (chunk, model) tuples.
    Bypasses the Priority Queue and Cache to deliver bytes immediately.
    """
    router = get_model_router()
    primary_model, fallback_model = router.get_models(model_tier)
    max_tokens = router.get_max_tokens(model_tier)

    messages: list[dict] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    if conversation_history:
        messages.extend(conversation_history)
    messages.append({"role": "user", "content": prompt})

    start = time.monotonic()
    
    # We yield directly from the fallback chain's generator
    async for chunk, model_used in stream_with_fallback(
        messages=messages,
        primary_model=primary_model,
        fallback_model=fallback_model,
        max_tokens=max_tokens,
    ):
        yield chunk, model_used
        
    latency_ms = int((time.monotonic() - start) * 1000)
    logger.info("LLM stream complete | tier=%s model=%s latency=%dms", model_tier, primary_model, latency_ms)

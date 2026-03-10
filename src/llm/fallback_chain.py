"""
src/llm/fallback_chain.py — Try primary model, fall back on errors/rate limits
"""

import asyncio
import httpx
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
from typing import Optional

from src.config.settings import OPENROUTER_API_KEY, OPENROUTER_BASE_URL
from src.llm.rate_limiter import get_rate_limiter
from src.utils.logging import get_logger

logger = get_logger(__name__)


async def _call_openrouter(
    model: str, messages: list[dict], max_tokens: int, response_format: Optional[dict] = None
) -> tuple[str, int]:
    """
    Make a single OpenRouter chat completion call.
    Returns (response_text, total_tokens).
    Raises httpx.HTTPStatusError on non-2xx.
    """
    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type((httpx.RequestError, httpx.TimeoutException)),
        reraise=True
    )
    async def _do_call():
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "HTTP-Referer": "https://github.com/Ksawyoux/ai-agent",
            "X-Title": "Personal AI Agent",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        if response_format:
            payload["response_format"] = response_format
            
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{OPENROUTER_BASE_URL}/chat/completions",
                headers=headers,
                json=payload,
            )
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as e:
                logger.error("OpenRouter error response: %s", e.response.text)
                raise
            data = resp.json()
            text = data["choices"][0]["message"]["content"]
            tokens = data.get("usage", {}).get("total_tokens", 0)
            return text, tokens

    return await _do_call()


async def call_with_fallback(
    messages: list[dict],
    primary_model: str,
    fallback_model: Optional[str],
    max_tokens: int,
    response_format: Optional[dict] = None,
) -> tuple[str, str, int]:
    """
    Try primary model; fall back to fallback_model on 429/5xx.
    Returns (response_text, model_used, total_tokens).
    """
    limiter = get_rate_limiter()
    await limiter.acquire()

    for model in filter(None, [primary_model, fallback_model]):
        try:
            logger.debug("Calling model: %s", model)
            text, tokens = await _call_openrouter(model, messages, max_tokens, response_format)
            logger.info("LLM call OK | model=%s tokens=%d", model, tokens)
            return text, model, tokens
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status == 429:
                limiter.trigger_cooldown()
                logger.warning("429 from %s — trying fallback", model)
            elif status >= 500:
                logger.warning("5xx from %s (%d) — trying fallback", model, status)
            else:
                raise
        except Exception as exc:
            logger.error("Unexpected error calling %s: %s", model, exc)
            raise

    raise RuntimeError(f"All models failed for call: primary={primary_model}, fallback={fallback_model}")


async def stream_with_fallback(
    messages: list[dict],
    primary_model: str,
    fallback_model: Optional[str],
    max_tokens: int,
    response_format: Optional[dict] = None,
):
    """
    Like call_with_fallback, but yields (chunk_text, model_used).
    Currently naive: just returns the full response as a single chunk because OpenRouter
    streaming requires parsing SSE which adds too much complexity here for now.
    But we expose the async generator signature so the caller can stream.
    """
    text, model, tokens = await call_with_fallback(
        messages, primary_model, fallback_model, max_tokens, response_format
    )
    # Simulate a stream by yielding the whole thing. 
    # To truly stream, we'd use httpx astream() and map SSE events.
    yield text, model
    # Return tokens as the last item or via some side-channel if strictly required,
    # but the caller usually recalculates tokens for streams anyway.

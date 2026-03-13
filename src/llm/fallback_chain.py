"""
src/llm/fallback_chain.py — Try primary model, fall back on errors/rate limits
"""

import asyncio
import httpx
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
from typing import Optional

from src.config.settings import OPENAI_API_KEY, OPENAI_BASE_URL
from src.llm.rate_limiter import get_rate_limiter
from src.utils.logging import get_logger

logger = get_logger(__name__)


async def _call_openai(
    model: str, messages: list[dict], max_tokens: int, response_format: Optional[dict] = None
) -> tuple[str, int]:
    """
    Make a single OpenAI chat completion call.
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
            "Authorization": f"Bearer {OPENAI_API_KEY}",
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
                f"{OPENAI_BASE_URL}/chat/completions",
                headers=headers,
                json=payload,
            )
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as e:
                logger.error("OpenAI error response: %s", e.response.text)
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
            text, tokens = await _call_openai(model, messages, max_tokens, response_format)
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
    Implement true streaming by parsing SSE chunks from the OpenAI API.
    """
    import json
    limiter = get_rate_limiter()
    await limiter.acquire()

    for model in filter(None, [primary_model, fallback_model]):
        try:
            logger.debug("Streaming model: %s", model)
            headers = {
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
                "stream": True,  # Enable SSE streaming
            }
            if response_format:
                payload["response_format"] = response_format
                
            async with httpx.AsyncClient(timeout=60.0) as client:
                async with client.stream(
                    "POST", 
                    f"{OPENAI_BASE_URL}/chat/completions", 
                    json=payload, 
                    headers=headers
                ) as response:
                    if response.status_code == 429:
                        limiter.trigger_cooldown()
                        logger.warning("429 from %s — trying fallback", model)
                        continue # try next model
                    elif response.status_code >= 500:
                        logger.warning("5xx from %s (%d) — trying fallback", model, response.status_code)
                        continue
                    
                    response.raise_for_status()

                    async for line in response.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            break
                            
                        try:
                            chunk_data = json.loads(data_str)
                            delta = chunk_data["choices"][0].get("delta", {})
                            content = delta.get("content")
                            if content:
                                yield content, model
                        except (json.JSONDecodeError, KeyError, IndexError):
                            pass

            logger.info("LLM stream OK | model=%s", model)
            return # successfully streamed
            
        except httpx.HTTPStatusError as exc:
            # Re-raise unless we are trying fallbacks handled above
            raise
        except Exception as exc:
            logger.error("Unexpected error streaming %s: %s", model, exc)
            raise

    raise RuntimeError(f"All models failed for stream: primary={primary_model}, fallback={fallback_model}")

"""
src/llm/openai_client.py — OpenAI client with automatic prefix caching
"""

import openai
from typing import Optional
from src.config.prompts import build_system_prompt
from src.config.settings import OPENAI_API_KEY, OPENAI_BASE_URL
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Initialize client
client = openai.AsyncOpenAI(
    api_key=OPENAI_API_KEY,
    base_url=OPENAI_BASE_URL,
)

async def chat_openai(
    user_message: str,
    tier: str = "agentic",
    user_facts: Optional[list] = None,
    servers: Optional[list] = None,
    active_task: Optional[dict] = None,
    history: Optional[list] = None,
    model: str = "gpt-4o",
    max_tokens: int = 4000,
    response_format: Optional[dict] = None,
):
    """
    OpenAI auto-caches matching prefixes ≥1024 tokens.
    Static blocks FIRST = stable prefix = cache hit.
    """
    system_prompt = build_system_prompt(
        user_facts=user_facts,
        connected_servers=servers,
        tier=tier,
        active_task=active_task,
    )

    messages = [{"role": "system", "content": system_prompt}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
    }
    if response_format:
        payload["response_format"] = response_format

    response = await client.chat.completions.create(**payload)

    # Check cache hit
    usage = response.usage
    cached_tokens = 0
    if hasattr(usage, 'prompt_tokens_details') and usage.prompt_tokens_details:
        cached_tokens = getattr(usage.prompt_tokens_details, 'cached_tokens', 0)
    
    logger.info("OpenAI call | model=%s cached_tokens=%d total_tokens=%d", model, cached_tokens, usage.total_tokens)
    print(f"Cached tokens: {cached_tokens}")

    return response.choices[0].message.content, usage.total_tokens

"""
src/utils/embeddings.py — Generate vector embeddings via sentence-transformers
Lazy-loaded to save memory until actually needed.
"""

import asyncio
from typing import Optional
from src.utils.logging import get_logger

logger = get_logger(__name__)

import httpx
from src.config.settings import OPENAI_API_KEY, OPENAI_BASE_URL

async def generate_embedding(text: str) -> Optional[list[float]]:
    """
    Generate a vector embedding for the given text using OpenAI API.
    Uses text-embedding-3-small (1536 dimensions).
    """
    if not OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY is not set. Cannot generate embeddings.")
        return None

    try:
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "text-embedding-3-small",
            "input": text,
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{OPENAI_BASE_URL}/embeddings",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["data"][0]["embedding"]
            
    except Exception as exc:
        logger.error("Failed to generate OpenAI embedding: %s", exc, exc_info=True)
        return None

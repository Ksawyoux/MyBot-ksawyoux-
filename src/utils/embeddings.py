"""
src/utils/embeddings.py — Generate vector embeddings via sentence-transformers
Lazy-loaded to save memory until actually needed.
"""

import asyncio
from typing import Optional
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Global model cache
_model = None
_model_lock = asyncio.Lock()


def _load_model_sync():
    """Synchronous model loading to be run in a thread."""
    from sentence_transformers import SentenceTransformer
    logger.info("Lazy-loading sentence-transformers model (all-MiniLM-L6-v2) in background thread...")
    return SentenceTransformer("all-MiniLM-L6-v2")


async def generate_embedding(text: str) -> Optional[list[float]]:
    """
    Generate a 384-dimensional vector embedding for the given text.
    Async-friendly: loads model and runs inference in a threadpool.
    """
    global _model
    
    async with _model_lock:
        if _model is None:
            try:
                _model = await asyncio.to_thread(_load_model_sync)
                logger.info("SentenceTransformer loaded successfully.")
            except ImportError:
                logger.error("sentence-transformers not installed. Embeddings disabled.")
                return None
            except Exception as exc:
                logger.error("Failed to load SentenceTransformer: %s", exc)
                return None

    try:
        # Run inference in a separate thread to avoid blocking the event loop
        vector = await asyncio.to_thread(_model.encode, text)
        return vector.tolist()
    except Exception as exc:
        logger.error("Failed to generate embedding: %s", exc, exc_info=True)
        return None

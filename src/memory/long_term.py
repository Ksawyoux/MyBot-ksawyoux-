"""
src/memory/long_term.py — Semantic search over long-term facts and summaries
"""

import json
from typing import Optional

from src.db.connection import get_db
from src.db.models import MemoryEmbedding
from src.utils.embeddings import generate_embedding
from src.utils.logging import get_logger
from src.config.settings import MEMORY_SEARCH_THRESHOLD as _DEFAULT_THRESHOLD

logger = get_logger(__name__)


async def store_long_term_memory(
    content: str, metadata: dict, memory_type: str = "fact"
) -> int:
    """Embed text and store it in the pgvector table."""
    vector = await generate_embedding(content)
    if not vector:
        logger.warning("Skipping memory storage — embeddings disabled or failed.")
        return -1

    try:
        with get_db() as db:
            mem = MemoryEmbedding(
                content=content,
                embedding=vector,
                metadata_json=metadata,
                type=memory_type
            )
            db.add(mem)
            db.commit()
            db.refresh(mem)
            return mem.id
    except Exception as exc:
        logger.error("Failed to store long-term memory: %s", exc)
        return -1


async def search_memory(query_text: str, limit: int = 5, threshold: float | None = None) -> list[dict]:
    """
    Search long-term memory using cosine similarity.
    Returns memories with a distance <= threshold (lower is better, 0 is exact match).
    """
    effective_threshold = threshold if threshold is not None else _DEFAULT_THRESHOLD
    vector = await generate_embedding(query_text)
    if not vector:
        return []

    try:
        with get_db() as db:
            distance_col = MemoryEmbedding.embedding.cosine_distance(vector).label("distance")
            rows = db.query(
                MemoryEmbedding.id,
                MemoryEmbedding.content,
                MemoryEmbedding.metadata_json,
                MemoryEmbedding.type,
                distance_col
            ).filter(
                MemoryEmbedding.embedding.cosine_distance(vector) <= effective_threshold
            ).order_by(distance_col).limit(limit).all()

            results = []
            for r in rows:
                results.append(
                    {
                        "id": r.id,
                        "content": r.content,
                        "metadata": r.metadata_json,
                        "type": r.type,
                        "distance": r.distance,
                    }
                )
            return results
    except Exception as exc:
        logger.error("Semantic search failed: %s", exc)
        return []

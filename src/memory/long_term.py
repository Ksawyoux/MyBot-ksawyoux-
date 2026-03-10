"""
src/memory/long_term.py — Semantic search over long-term facts and summaries
"""

import json
from typing import Optional

from sqlalchemy import text
from src.db.connection import get_db
from src.utils.embeddings import generate_embedding
from src.utils.logging import get_logger

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
            row = db.execute(
                text(
                    "INSERT INTO memory_embeddings (content, embedding, metadata, type) "
                    "VALUES (:content, :emb, :meta, :type) RETURNING id"
                ),
                {
                    "content": content,
                    # Convert list to string format required by pgvector: '[1.1, 2.2, ...]'
                    "emb": f"[{','.join(str(f) for f in vector)}]",
                    "meta": json.dumps(metadata),
                    "type": memory_type,
                },
            ).fetchone()
            return row[0] if row else -1
    except Exception as exc:
        logger.error("Failed to store long-term memory: %s", exc)
        return -1


async def search_memory(query_text: str, limit: int = 5, threshold: float = 0.5) -> list[dict]:
    """
    Search long-term memory using cosine similarity.
    Returns memories with a distance <= threshold (lower is better, 0 is exact match).
    """
    vector = await generate_embedding(query_text)
    if not vector:
        return []

    try:
        v_str = f"[{','.join(str(f) for f in vector)}]"
        with get_db() as db:
            rows = db.execute(
                text(
                    "SELECT id, content, metadata, type, embedding <=> :emb AS distance "
                    "FROM memory_embeddings "
                    "WHERE embedding <=> :emb <= :thresh "
                    "ORDER BY distance ASC LIMIT :lim"
                ),
                {"emb": v_str, "thresh": threshold, "lim": limit},
            ).fetchall()

            results = []
            for r in rows:
                results.append(
                    {
                        "id": r[0],
                        "content": r[1],
                        "metadata": r[2],
                        "type": r[3],
                        "distance": float(r[4]),
                    }
                )
            return results
    except Exception as exc:
        logger.error("Semantic search failed: %s", exc)
        return []

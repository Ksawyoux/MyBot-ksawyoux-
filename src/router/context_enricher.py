"""
src/router/context_enricher.py — Inject relevant facts into the prompt
"""

from src.memory.long_term import search_memory
from src.utils.logging import get_logger

logger = get_logger(__name__)


async def enrich_prompt_with_context(prompt: str) -> str:
    """
    Search for long-term facts relevant to the user's prompt
    and prepend them as context.
    """
    relevant_memories = await search_memory(prompt, limit=3, threshold=0.6)

    if not relevant_memories:
        return prompt

    mem_lines = ["\n[Context from previous conversations]"]
    for mem in relevant_memories:
        mem_lines.append(f"- {mem['content']}")
    mem_lines.append("[End of context]\n")

    enriched = "\n".join(mem_lines) + f"\nUser: {prompt}"
    logger.debug("Enriched prompt with %d memories", len(relevant_memories))
    return enriched

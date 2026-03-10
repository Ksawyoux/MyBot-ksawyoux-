"""
src/memory/fact_extractor.py — Extract permanent facts from conversations
"""

import json
from sqlalchemy import text
from src.db.connection import get_db
from src.memory.long_term import store_long_term_memory
from src.utils.logging import get_logger

logger = get_logger(__name__)

EXTRACTOR_SYSTEM_PROMPT = """
Analyze this conversation and extract explicit, permanent facts about the user.
Categories:
- "preference" (likes/dislikes, physical environment preferences)
- "knowledge" (facts about the user: name, job, location, family)
- "pattern" (recurring habits: wakes up at 7am, travels on Tuesdays)

Return ONLY a JSON list of objects matching this schema exactly:
[
  {
    "category": "preference|knowledge|pattern",
    "key": "short_topic_key_like_favorite_color",
    "value": "The actual fact content"
  }
]
If there are no new facts, return []. DO NOT include conversational filler, just the JSON.
"""


async def extract_and_store_facts(session_id: str, messages: list[dict]) -> int:
    """
    Send conversation to LLM to extract JSON facts.
    Save them to the 'facts' table and embed them in 'memory_embeddings'.
    Returns number of facts extracted.
    """
    from src.llm.gateway import complete

    if len(messages) < 2:
        return 0

    conv_text = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in messages)

    try:
        result = await complete(
            prompt=conv_text,
            model_tier="system",
            system_prompt=EXTRACTOR_SYSTEM_PROMPT,
            use_cache=False,
        )

        response = result["response"].strip()

        # Handle formatting weirdness (LLM might wrap in markdown blocks)
        if response.startswith("```json"):
            response = response[7:]
        if response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]

        parsed: list[dict] = json.loads(response.strip())
        if not parsed:
            return 0

        saved = 0
        with get_db() as db:
            for fact in parsed:
                cat = fact.get("category", "knowledge")
                key = fact.get("key", "unknown")
                val = fact.get("value", "")

                if not val:
                    continue

                # Quick conflict check (skip exact matches)
                exist = db.execute(
                    text(
                        "SELECT id FROM facts WHERE category = :cat AND key = :key AND value = :val AND superseded_by IS NULL"
                    ),
                    {"cat": cat, "key": key, "val": val},
                ).fetchone()

                if exist:
                    continue

                # Save fact
                row = db.execute(
                    text(
                        "INSERT INTO facts (category, key, value, source_session) "
                        "VALUES (:cat, :key, :val, :sid) RETURNING id"
                    ),
                    {"cat": cat, "key": key, "val": val, "sid": session_id},
                ).fetchone()
                fact_id = row[0]

                # Store vector embedding
                await store_long_term_memory(
                    content=f"User {cat} - {key}: {val}",
                    metadata={"fact_id": fact_id, "category": cat, "key": key},
                    memory_type="fact",
                )
                saved += 1

        if saved > 0:
            logger.info("Extracted %d new facts from session %s", saved, session_id[:8])
        return saved

    except json.JSONDecodeError:
        logger.warning("Fact extractor returned invalid JSON: %s", response[:100])
        return 0
    except Exception as exc:
        logger.error("Fact extraction failed: %s", exc)
        return 0

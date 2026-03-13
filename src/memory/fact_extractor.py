"""
src/memory/fact_extractor.py — Extract permanent facts from conversations
"""

import json
from src.db.connection import get_db
from src.db.models import Fact
from src.memory.long_term import store_long_term_memory
from src.utils.logging import get_logger
from src.config.prompts import EXTRACTOR_SYSTEM_PROMPT

logger = get_logger(__name__)

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
        # Prompt needs a tiny tweak to return an object because JSON mode often requires a root object
        system_prompt = EXTRACTOR_SYSTEM_PROMPT.replace(
            "Return ONLY a JSON list of objects", 
            "Return ONLY a JSON object with a 'facts' key containing a list of objects"
        )
        
        result = await complete(
            prompt=conv_text,
            model_tier="system",
            system_prompt=system_prompt,
            use_cache=False,
            response_format={"type": "json_object"}
        )

        response = result["response"]
        parsed_obj: dict = json.loads(response.strip())
        
        # Fallback if model just returns a list anyway
        if isinstance(parsed_obj, list):
            parsed = parsed_obj
        else:
            parsed = parsed_obj.get("facts", [])
            
        if not parsed:
            return 0

        saved = 0
        with get_db() as db:
            for fact_data in parsed:
                cat = fact_data.get("category", "knowledge")
                key = fact_data.get("key", "unknown")
                val = fact_data.get("value", "")

                if not val:
                    continue

                # Quick conflict check (skip exact matches)
                exist = db.query(Fact).filter(
                    Fact.category == cat,
                    Fact.key == key,
                    Fact.value == val,
                    Fact.superseded_by == None
                ).first()

                if exist:
                    continue

                # Save fact
                fact = Fact(
                    category=cat,
                    key=key,
                    value=val,
                    source_session=session_id
                )
                db.add(fact)
                db.flush() # Flush to get fact ID for embeddings, but don't commit yet
                fact_id = fact.id

                # Store vector embedding
                await store_long_term_memory(
                    content=f"User {cat} - {key}: {val}",
                    metadata={"fact_id": fact_id, "category": cat, "key": key},
                    memory_type="fact",
                )
                saved += 1
            
            # Commit the entire batch of facts and embeddings atomically
            db.commit()

        if saved > 0:
            logger.info("Extracted %d new facts from session %s", saved, session_id[:8])
        return saved

    except json.JSONDecodeError:
        logger.warning("Fact extractor returned invalid JSON: %s", result.get("response", "")[:100])
        return 0
    except Exception as exc:
        logger.error("Fact extraction failed: %s", exc)
        return 0

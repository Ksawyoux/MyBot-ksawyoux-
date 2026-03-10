"""
src/memory/summarizer.py — Compress long conversations via LLM
"""

from src.db.connection import get_db
from src.db.models import Summary, Conversation
from src.utils.logging import get_logger
from src.utils.tokens import count_tokens

logger = get_logger(__name__)

SUMMARIZE_SYSTEM_PROMPT = (
    "You are a memory manager. Summarize the following conversation into a compact, "
    "factual paragraph that captures key decisions, preferences, and facts mentioned. "
    "Be concise — max 200 words."
)


async def summarize_session(session_id: str, messages: list[dict]) -> str | None:
    """
    Summarize messages for a session using the LLM.
    Stores the summary and marks messages as summarized.
    Returns the summary text, or None on failure.
    """
    from src.llm.gateway import complete

    if not messages:
        return None

    # Build conversation text for summarization
    conv_text = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in messages)

    try:
        result = await complete(
            prompt=conv_text,
            model_tier="system",
            system_prompt=SUMMARIZE_SYSTEM_PROMPT,
            use_cache=False,
        )
        summary_text = result["response"]
        tokens = count_tokens(summary_text)

        with get_db() as db:
            # Save summary
            summary = Summary(
                session_id=session_id,
                content=summary_text,
                tokens=tokens
            )
            db.add(summary)
            db.commit()
            db.refresh(summary)

            # Mark messages as summarized
            db.query(Conversation).filter(
                Conversation.session_id == session_id,
                Conversation.summarized == False
            ).update({
                Conversation.summarized: True,
                Conversation.summary_id: summary.id
            }, synchronize_session=False)
            db.commit()

        logger.info("Summarized session %s → %d tokens", session_id[:8], tokens)
        return summary_text

    except Exception as exc:
        logger.error("Summarization failed for session %s: %s", session_id[:8], exc)
        return None

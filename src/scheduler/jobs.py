"""
src/scheduler/jobs.py — Callable functions that the scheduler executes
"""

import asyncio
from src.utils.logging import get_logger

logger = get_logger(__name__)


def run_scheduled_agent_task(session_id: str, prompt: str) -> None:
    """
    This function is called by APScheduler on trigger.
    It injects a message into the event loop to be processed as if the user sent it.
    """
    logger.info("Running scheduled task for session %s: %s", session_id[:8], prompt)
    
    # We must run the async gateway from this synchronous APScheduler thread
    from src.db.tasks import create_task, update_task
    from src.router.task_classifier import classify_task
    from src.llm.gateway import complete
    
    async def _execute():
        classification = await classify_task(prompt)
        task_type = classification["type"]
        # Force it to be a normal/complex task, not 'scheduled' again
        if task_type == "scheduled":
            task_type = "complex"
            
        task_id = create_task(task_type, {"session_id": session_id, "prompt": prompt}, priority=2)
        update_task(task_id, status="in_progress")
        
        try:
            if task_type == "simple":
                result = await complete(prompt=prompt, model_tier="lightweight")
                response_text = result["response"]
            else:
                from src.agents.crew_manager import execute_crew_task
                response_text = await execute_crew_task(classification["intent"], prompt, task_id)
                
            update_task(task_id, status="completed", output_data={"response": response_text[:500]})
            
            # Send the result to the user via Telegram
            from src.config.settings import TELEGRAM_ADMIN_USER_ID, TELEGRAM_BOT_TOKEN
            from telegram import Bot
            bot = Bot(token=TELEGRAM_BOT_TOKEN)
            await bot.send_message(
                chat_id=TELEGRAM_ADMIN_USER_ID, 
                text=f"⏰ *Scheduled Task Complete*\n_Prompt: {prompt}_\n\n{response_text}",
                parse_mode="Markdown"
            )
            
        except Exception as exc:
            logger.error("Scheduled task failed: %s", exc)
            update_task(task_id, status="failed", error_message=str(exc))

    # Run in a new event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_execute())
    finally:
        loop.close()


def run_morning_briefing(session_id: str) -> None:
    """
    This function is called by APScheduler every morning at 08:00.
    It runs the BriefingAgent to synthesize emails and calendars.
    """
    logger.info("Running morning briefing for session %s", session_id[:8])
    
    from src.db.tasks import create_task, update_task
    from src.agents.crew_manager import execute_crew_task
    
    async def _execute():
        from src.memory.short_term import get_short_term_context
        from src.router.context_enricher import enrich_prompt_with_context
        
        # Pull recent conversation memory for immediate context
        history, _ = get_short_term_context(session_id, limit=5)
        recent_context = "\n".join([f"{m['role']}: {m['content']}" for m in history]) if history else "No recent conversations."
        
        # Pull long-term memory specifically tailored for mornings or preferences
        enriched_prefs = await enrich_prompt_with_context("what are my morning routine preferences, goals, and schedule constraints?")
        
        prompt = (
            f"Fetch my meetings and emails for today and prepare the morning digest.\n\n"
            f"--- RECENT CONVERSATIONS ---\n{recent_context}\n\n"
            f"--- LONG-TERM PREFERENCES ---\n{enriched_prefs}"
        )
        task_id = create_task("complex", {"session_id": session_id, "prompt": prompt}, priority=2)
        update_task(task_id, status="in_progress")
        
        try:
            # Fake the intent structure to force the crew manager to route to briefing
            intent = {"action": "briefing"}
            response_text = await execute_crew_task(intent, prompt, task_id)
            update_task(task_id, status="completed", output_data={"response": response_text[:500]})
            
            # Send the result to the user via Telegram
            from src.config.settings import TELEGRAM_ADMIN_USER_ID, TELEGRAM_BOT_TOKEN
            from telegram import Bot
            bot = Bot(token=TELEGRAM_BOT_TOKEN)
            await bot.send_message(
                chat_id=TELEGRAM_ADMIN_USER_ID, 
                text=f"🌅 *Your Morning Briefing*\n\n{response_text}",
                parse_mode="Markdown"
            )
            
        except Exception as exc:
            logger.error("Morning briefing failed: %s", exc)
            update_task(task_id, status="failed", error_message=str(exc))

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_execute())
    finally:
        loop.close()

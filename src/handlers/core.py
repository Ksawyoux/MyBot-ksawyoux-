"""
src/handlers/core.py — Core message handlers for the routing system
"""

from typing import Dict, Any
from src.utils.logging import get_logger
from src.llm.gateway import complete
from src.output.templates.responses.simple_answer import SimpleAnswerTemplate
from src.output.templates.responses.structured_result import StructuredResultTemplate
from src.output.templates.errors.error import ErrorTemplate
from src.router.router import handle_internal_query as internal_query_handler
from src.agents.pipeline import crew_pipeline as agentic_pipeline

logger = get_logger(__name__)

async def fast_respond(user_msg: str, context: dict):
    """Simple LLM response for social or lightweight queries."""
    # We need access to history and system prompt here. 
    # Context should probably carry these or we fetch them.
    # For now, we'll assume context has what we need or we fetch minimal context.
    
    # REFACTOR NOTE: This needs to be fleshed out to match MessageProcessor's current 'simple' block.
    # Passing through to a generic agentic respond for now until full context injection is ready.
    return await agentic_respond(user_msg, context, tier="lightweight")

async def handle_internal_query(user_msg: str, context: dict):
    """Direct DB/System query handler."""
    return await internal_query_handler(user_msg, context)

async def crew_pipeline(user_msg: str, context: dict):
    """Multi-agent execution."""
    return await agentic_pipeline(user_msg, context)

async def agentic_respond(user_msg: str, context: dict, tier: str = "capable"):
    """Reasoning-heavy single agent response."""
    # Similar to fast_respond but with a higher tier model.
    result = await complete(
        prompt=user_msg,
        model_tier=tier,
        system_prompt=context.get("system_prompt", "You are a helpful assistant."),
        conversation_history=context.get("history", []),
        priority=0,
        metadata=context.get("metadata", {})
    )
    return result["response"]

async def handle_scheduling(user_msg: str, context: dict):
    """Logic to parse and set up cron jobs."""
    # Extracted from MessageProcessor.process_message 'scheduled' block
    from src.scheduler.engine import get_scheduler
    from src.scheduler.jobs import run_scheduled_agent_task
    from apscheduler.triggers.cron import CronTrigger
    
    session_id = context.get("session_id")
    
    extract_prompt = f"Convert this request into a cron expression and a clean prompt string.\nRequest: {user_msg}\nOutput FORMAT EXACTLY like this:\nCRON: * * * * *\nPROMPT: task description"
    
    result = await complete(
        prompt=extract_prompt,
        model_tier="lightweight",
        system_prompt="You are a strict cron job parser. Reply ONLY with the requested format.",
    )
    
    lines = result["response"].strip().split('\n')
    cron_expr = None
    task_prompt = user_msg
    
    for line in lines:
        if line.startswith("CRON:"):
            cron_expr = line.replace("CRON:", "").strip()
        elif line.startswith("PROMPT:"):
            task_prompt = line.replace("PROMPT:", "").strip()
            
    if not cron_expr:
        return "❌ Could not understand the schedule format."
        
    try:
        trigger = CronTrigger.from_crontab(cron_expr)
        scheduler = get_scheduler()
        job = scheduler.add_job(
            run_scheduled_agent_task,
            trigger=trigger,
            args=[session_id, task_prompt],
            name=f"User Task: {task_prompt[:30]}"
        )
        return f"⏰ Job Scheduled\nID: {job.id}\nSchedule: {cron_expr}\nTask: {task_prompt}"
    except Exception as e:
        logger.error(f"Scheduling failed: {e}")
        return f"❌ Scheduling error: {str(e)}"

# Registry Helper
def register_core_handlers():
    from src.config.routing import register_handler
    register_handler("fast_respond", fast_respond)
    register_handler("handle_internal_query", handle_internal_query)
    register_handler("crew_pipeline", crew_pipeline)
    register_handler("agentic_respond", agentic_respond)
    register_handler("handle_scheduling", handle_scheduling)
    # Placeholder for tool handlers
    # ...

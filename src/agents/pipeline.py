"""
src/agents/pipeline.py — Multi-agent pipeline with pre-flight guardrails and checkpointing
"""

from typing import Dict, Any
from src.utils.logging import get_logger
from src.router.router import handle_internal_query
from src.agents.crew_manager import execute_crew_task

logger = get_logger(__name__)


async def crew_pipeline(user_msg: str, context: dict):
    """
    Multi-agent pipeline for HIGH complexity tasks.
    Checkpoints are written after each stage so a restart can resume
    rather than re-running the full pipeline from scratch.
    """
    from src.db.tasks import save_checkpoint, load_checkpoint

    task_id = context.get("task_id", 0)

    # ── RESUME FROM CHECKPOINT ───────────────────────────────
    ckpt = load_checkpoint(task_id) if task_id else None
    if ckpt:
        stage = ckpt.get("stage")
        logger.info("Resuming task %d from checkpoint stage=%s", task_id, stage)
        if stage == "crew_done":
            # Already finished — return cached result
            return ckpt.get("result", "")
        if stage == "planned":
            # Skip planner, go straight to crew
            plan = ckpt.get("plan", {})
            intent = plan.get("intent", {"action": "other", "tier": "agentic"})
            result = await execute_crew_task(intent, user_msg, task_id)
            if task_id:
                save_checkpoint(task_id, {"stage": "crew_done", "result": result})
            return result

    # ── PRE-FLIGHT GUARD ─────────────────────────────────────
    if _is_internal_query(user_msg):
        logger.info("Pre-flight: internal query detected, skipping agents.")
        return await handle_internal_query(user_msg, context)

    # ── PLANNER ──────────────────────────────────────────────
    plan = await run_planner(user_msg, context)
    if task_id:
        save_checkpoint(task_id, {"stage": "planned", "plan": plan})

    if plan.get("data_source") == "internal":
        logger.info("Planner redirect: internal data request.")
        return await handle_internal_query(user_msg, context)

    # ── EXECUTE PIPELINE ─────────────────────────────────────
    intent = plan.get("intent", {"action": "other", "tier": "agentic"})
    result = await execute_crew_task(intent, user_msg, task_id)
    if task_id:
        save_checkpoint(task_id, {"stage": "crew_done", "result": result})
    return result
    

async def run_planner(user_msg: str, context: dict) -> Dict[str, Any]:
    """
    A lightweight internal planner to determine if a task can be handled
    by internal data sources or needs full agentic reasoning.
    """
    from src.router.intent_parser import parse_intent
    
    intent = await parse_intent(user_msg)
    
    # Heuristic: If it's a social or internal-style action but reached here,
    # mark it as internal data source.
    is_internal = intent.get("action") == "internal_query" or intent.get("tier") == "fast"
    
    return {
        "data_source": "internal" if is_internal else "agentic",
        "intent": intent
    }


def _is_internal_query(msg: str) -> bool:
    """Fast keyword check to catch obvious internal queries."""
    internal_keywords = [
        "my tasks", "my reminders", "my schedule", "scheduled tasks",
        "my memory", "what do you know", "my jobs", "pending tasks",
        "show me my", "list my", "what are my",
    ]
    msg_lower = msg.lower()
    return any(kw in msg_lower for kw in internal_keywords)

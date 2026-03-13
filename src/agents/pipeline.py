"""
src/agents/pipeline.py — Multi-agent pipeline with pre-flight guardrails
"""

from typing import Dict, Any
from src.utils.logging import get_logger
from src.router.router import handle_internal_query
from src.agents.crew_manager import execute_crew_task

logger = get_logger(__name__)

async def crew_pipeline(user_msg: str, context: dict):
    """
    Multi-agent pipeline for HIGH complexity tasks.
    Includes pre-flight check to prevent misrouted simple queries.
    """
    
    # ── PRE-FLIGHT GUARD ─────────────────────────────────────
    # Catch any misrouted simple queries before spinning up agents
    if _is_internal_query(user_msg):
        logger.info("Pre-flight check: Obvious internal query detected. Routing to internal handler.")
        # Don't waste tokens on CrewAI — handle directly
        return await handle_internal_query(user_msg, context)
    
    # ── PLANNER ──────────────────────────────────────────────
    # run_planner helps refine the execution strategy
    plan = await run_planner(user_msg, context)
    
    # Check if planner says this is internal
    if plan.get("data_source") == "internal":
        logger.info("Planner redirect: Task identified as internal data request.")
        return await handle_internal_query(user_msg, context)
    
    # ── EXECUTE PIPELINE ─────────────────────────────────────
    # Convert context to expected intent structure or pass context
    # Note: execute_crew_task expects (intent, prompt, task_id)
    # We'll pull intent from the plan or context if available
    intent = plan.get("intent", {"action": "other", "tier": "agentic"})
    task_id = context.get("task_id", 0)
    
    return await execute_crew_task(intent, user_msg, task_id)
    

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

"""
src/router/router.py — Core routing engine for ksawyoux
Handles hybrid routing: Internal Data (Fast) vs LLM (Agentic)
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from src.utils.logging import get_logger
from src.scheduler.engine import get_scheduler
from src.db.connection import get_db
from src.db.models import Fact
from sqlalchemy import text

logger = get_logger(__name__)

async def route_message(user_msg: str, intent: dict, context: dict) -> Optional[str]:
    """
    Route based on intent classification.
    CRITICAL: Internal queries never hit CrewAI pipeline.
    
    Returns a string if handled internally, or None to proceed to LLM.
    """
    tier = intent.get("tier", "agentic")
    action = intent.get("action", "other")
    complexity = intent.get("complexity", "low")
    
    # ── FAST TIER ──────────────────────────────────────────────
    if tier == "fast":
        if action == "internal_query" or any(kw in user_msg.lower() for kw in ["scheduled", "tasks", "memory", "know about me"]):
            result = await handle_internal_query(user_msg, context)
            if result:
                return result
        
        # Social handling will happen in MessageProcessor (fast respond)
        return None
    
    # ── SCHEDULED TIER ─────────────────────────────────────────
    if tier == "scheduled":
        # Scheduling setup still needs LLM to parse cron
        return None
    
    # ── AGENTIC TIER ───────────────────────────────────────────
    # All agentic tiers (low/med/high complexity) return None to hit LLM/CrewAI
    return None


async def handle_internal_query(user_msg: str, context: dict) -> Optional[str]:
    """
    Handles requests for internal data:
    - Scheduled tasks (from APScheduler)
    - Memory/facts (from pgvector/Postgres)
    """
    msg_lower = user_msg.lower()
    
    # 1. Scheduled tasks
    if any(kw in msg_lower for kw in ["scheduled", "tasks", "reminders", "jobs"]):
        tasks = await get_scheduled_tasks()
        
        if not tasks:
            return "No scheduled tasks right now. Want me to set one up?"
        
        lines = ["*📋 Your Scheduled Tasks:*\n"]
        for task in tasks:
            status_icon = "✅" if task["active"] else "⏸️"
            lines.append(
                f"{status_icon} `{task['id']}` — {task['description']}\n"
                f"   ⏰ {task['schedule']} | Next: `{task['next_run']}`"
            )
        return "\n".join(lines)
    
    # 2. Memory query
    if any(kw in msg_lower for kw in ["know about me", "memory", "remember"]):
        facts = await get_user_facts()
        
        if not facts:
            return "I haven't learned much about you yet. Tell me more!"
        
        lines = ["*🧠 What I know about you:*\n"]
        for fact in facts:
            lines.append(f"• *{fact['key']}*: {fact['value']}")
        return "\n".join(lines)
    
    return None


async def get_scheduled_tasks() -> List[Dict[str, Any]]:
    """Helper to fetch jobs from APScheduler."""
    try:
        scheduler = get_scheduler()
        jobs = scheduler.get_jobs()
        
        results = []
        for j in jobs:
            results.append({
                "id": j.id,
                "description": j.name,
                "schedule": str(j.trigger),
                "next_run": j.next_run_time.strftime("%H:%M %b %d") if j.next_run_time else "Paused",
                "active": j.next_run_time is not None
            })
        return results
    except Exception as e:
        logger.error("Failed to fetch scheduled tasks: %s", e)
        return []


async def get_user_facts() -> List[Dict[str, Any]]:
    """Helper to fetch level 1 facts from Postgres."""
    try:
        with get_db() as db:
            facts = db.query(Fact).filter(Fact.superseded_by == None).all()
            return [{"key": f.key, "value": f.value} for f in facts]
    except Exception as e:
        logger.error("Failed to fetch user facts: %s", e)
        return []

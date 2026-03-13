"""
src/config/routing.py — Explicit routing map action → handler
Prevents the "everything goes to CrewAI" problem.
"""

from typing import Dict, Any, Callable, Optional

# Registry to hold actual callable functions. 
# Populated at runtime to avoid circular imports.
HANDLER_REGISTRY: Dict[str, Callable] = {}

ACTION_HANDLERS = {
    # ── FAST (No LLM pipeline needed) ──────────────────────
    "social":         "fast_respond",
    "internal_query": "handle_internal_query",
    "clarify":        "fast_respond",
    
    # ── DIRECT TOOL USE (Single tool, no pipeline) ─────────
    "email":          "tool_email",
    "calendar":       "tool_calendar",
    "file":           "tool_filesystem",
    "code":           "tool_github",
    
    # ── SEARCH (May need researcher agent) ─────────────────
    "search":         "agentic_search",      # Single agent
    "research":       "crew_pipeline",        # Multi-agent only for deep research
    
    # ── SCHEDULING (Internal + optional calendar) ──────────
    "reminder":       "handle_scheduling",
    
    # ── COMPLEX (Multi-agent) ──────────────────────────────
    "plan":           "crew_pipeline",
    "web_browse":     "handle_web_browse",
    
    # ── FALLBACK ───────────────────────────────────────────
    "other":          "agentic_respond",
}


async def route_by_action(intent: dict, user_msg: str, context: dict):
    """Route to the correct handler based on classified action."""
    action = intent.get("action", "other")
    complexity = intent.get("complexity", "low")
    
    handler_name = ACTION_HANDLERS.get(action, "agentic_respond")
    
    # Override: only "research" and "plan" with HIGH complexity
    # should ever reach crew_pipeline
    if handler_name == "crew_pipeline" and complexity != "high":
        handler_name = "agentic_respond"
    
    if handler_name not in HANDLER_REGISTRY:
        from src.utils.logging import get_logger
        logger = get_logger(__name__)
        logger.warning(f"Handler {handler_name} not found in registry. Falling back to agentic_respond.")
        handler_name = "agentic_respond"

    handler = HANDLER_REGISTRY.get(handler_name)
    if not handler:
         raise ValueError(f"Critical Error: No handler found for {handler_name}")
         
    return await handler(user_msg, context)


def register_handler(name: str, handler: Callable):
    """Register a function as a routing handler."""
    HANDLER_REGISTRY[name] = handler

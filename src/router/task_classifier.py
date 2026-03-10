"""
src/router/task_classifier.py — Route tasks based on intent
"""

from src.router.intent_parser import parse_intent
from src.utils.logging import get_logger

logger = get_logger(__name__)


async def classify_task(prompt: str) -> dict:
    """
    Classify a user prompt to determine execution path.
    Returns:
    {
      "type": "simple|complex|scheduled",
      "priority": 0|1|2|3,
      "intent": <dict from intent_parser>
    }
    """
    intent = await parse_intent(prompt)

    # Determine type
    task_type = "complex"
    action = intent.get("action", "").lower()
    complexity_hint = intent.get("complexity_hint", "").lower()

    if action == "schedule":
        task_type = "scheduled"
    elif complexity_hint == "simple":
        # Unless it specifically asked for a complex tool, trust the simple hint
        if action not in ("email", "calendar", "search", "skill"):
            task_type = "simple"

    # Determine queue priority (0=highest)
    if action == "schedule":
        priority = 3  # Scheduled setup is low priority
    elif intent.get("urgency", "").lower() == "high":
        priority = 0
    elif task_type == "simple":
        priority = 0  # Fast, interactive Q&A
    else:
        priority = 1  # Standard work

    logger.info("Classified prompt as %s (priority %d)", task_type, priority)

    return {
        "type": task_type,
        "priority": priority,
        "intent": intent,
    }

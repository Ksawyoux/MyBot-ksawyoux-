"""
src/router/intent_parser.py — Extract intent, urgency, and entities from user input
"""

import json
import re
import traceback
from src.utils.logging import get_logger
from src.config.prompts import INTENT_SYSTEM_PROMPT

logger = get_logger(__name__)

def get_dynamic_system_prompt() -> str:
    import os
    skills_dir = os.path.join(os.path.dirname(__file__), "..", "skills")
    skills_context = ""
    
    if os.path.exists(skills_dir):
        from src.agents.skill_loader import parse_skill_markdown
        skills = []
        for item in os.listdir(skills_dir):
            skill_path = os.path.join(skills_dir, item)
            if os.path.isdir(skill_path):
                skill_file = os.path.join(skill_path, "SKILL.md")
                if os.path.exists(skill_file):
                    parsed = parse_skill_markdown(skill_file)
                    # We use the folder name as the key/identifier for reliability
                    skills.append(f"- {item}: {parsed.get('description', '')}")
        
        if skills:
            skills_context = "\n\nInstalled Skills available for action='skill':\n" + "\n".join(skills)
            
    base_prompt = INTENT_SYSTEM_PROMPT
    if skills_context:
        base_prompt = base_prompt.replace(
            '"action":"social|internal_query|email|calendar|search|file|code|reminder|research|plan|clarify|web_browse|skill|other"',
            '"action":"social|internal_query|email|calendar|search|file|code|reminder|research|plan|clarify|web_browse|skill|other",\n  "skill_name": "folder name of skill if action is skill (from list below)"'
        )
        base_prompt += skills_context
        
    return base_prompt


def _clean_json_response(text: str) -> str:
    """Clean common LLM JSON formatting issues."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]) if len(lines) > 2 else lines[1]
    # Remove trailing comma before closing brace/bracket
    text = re.sub(r',\s*}', '}', text)
    text = re.sub(r',\s*\]', ']', text)
    return text.strip()

def _validate_intent(intent: dict, user_msg: str) -> dict:
    """Validate and fix intent fields."""
    required = {"tier", "action", "requires_tools"}
    fixed = {}
    
    tier = str(intent.get("tier", "")).lower()
    if tier not in ("fast", "agentic", "scheduled"):
        logger.warning("Invalid tier '%s' for: %s", tier, user_msg)
        if any(word in user_msg.lower() for word in ["hello", "hi", "hey", "yo", "sup"]):
            tier = "fast"
        else:
            tier = "fast"
    fixed["tier"] = tier
    
    action = str(intent.get("action", "")).lower()
    valid_actions = {
        "social", "internal_query", "email", "calendar",
        "search", "file", "code", "reminder", "research",
        "plan", "clarify", "web_browse", "skill", "other"
    }
    if action not in valid_actions:
        logger.warning("Invalid action '%s' for: %s", action, user_msg)
        action = "other"
    fixed["action"] = action
    
    fixed["requires_tools"] = bool(intent.get("requires_tools", False))
    
    complexity = str(intent.get("complexity", "")).lower()
    if complexity not in ("low", "medium", "high"):
        complexity = "low" if tier == "fast" else "medium"
    fixed["complexity"] = complexity
    
    # Backward compatibility mapping
    fixed["complexity_hint"] = "simple" if fixed["tier"] == "fast" else "complex"
    fixed["urgency"] = intent.get("urgency", "normal")
    fixed["entities"] = intent.get("entities", [])
    fixed["skill_name"] = intent.get("skill_name", "")
    fixed["thought"] = intent.get("thought", "Validated from LLM output")
    
    return fixed

def _fallback_classify(user_msg: str) -> dict:
    """Pattern-based fallback classifier if everything fails."""
    user_msg_lower = user_msg.lower()
    
    # Social
    if any(w in user_msg_lower for w in ["yo", "sup", "hello", "hi", "hey", "how's it going"]):
        action = "social"
        tier = "fast"
    # Internal query
    elif any(phrase in user_msg_lower for phrase in ["my tasks", "my scheduled tasks", "know about me", "my reminders"]):
        action = "internal_query"
        tier = "fast"
    # Tools/Search/Agentic
    elif "remind me" in user_msg_lower or "set a reminder" in user_msg_lower:
        action = "reminder"
        tier = "scheduled"
    elif "email" in user_msg_lower:
        action = "email"
        tier = "agentic"
    elif "calendar" in user_msg_lower:
        action = "calendar"
        tier = "agentic"
    elif "search" in user_msg_lower or "research" in user_msg_lower:
        action = "research" if "research" in user_msg_lower else "search"
        tier = "agentic"
    elif "plan" in user_msg_lower:
        action = "plan"
        tier = "agentic"
    elif "http" in user_msg_lower or "www." in user_msg_lower or "browse" in user_msg_lower:
        action = "web_browse"
        tier = "agentic"
    else:
        action = "other"
        tier = "fast"  # Start with fast to be cheaper as fallback

    return {
        "tier": tier,
        "action": action,
        "requires_tools": tier == "agentic",
        "complexity": "low" if tier in ("fast", "scheduled") else "medium",
        "complexity_hint": "simple" if tier == "fast" else "complex",
        "urgency": "normal",
        "entities": [],
        "skill_name": "",
        "thought": "Fallback pattern match"
    }


async def parse_intent(prompt: str) -> dict:
    """
    Call the LLM (lightweight tier) to parse user intent.
    Returns a dict with action, urgency, entities, tier, and requires_tools.
    """
    from src.llm.gateway import complete

    logger.info("🔍 CLASSIFYING: %s", prompt)

    try:
        result = await complete(
            prompt=prompt,
            model_tier="lightweight",
            system_prompt=get_dynamic_system_prompt(),
            use_cache=True,
            response_format={"type": "json_object"}
        )

        response = result["response"]
        logger.info("🤖 RAW LLM OUTPUT: %s", response)
        
        cleaned = _clean_json_response(response)
        parsed = json.loads(cleaned)
        
        intent = _validate_intent(parsed, prompt)
        
        logger.info("✅ PARSED: %s", intent)
        return intent

    except Exception as exc:
        logger.error("❌ CLASSIFIER FAILED: %s", exc)
        logger.debug("   RAW RESPONSE: %s", result.get("response", "No response object") if 'result' in locals() else "Unknown")
        logger.debug(traceback.format_exc())
        return _fallback_classify(prompt)

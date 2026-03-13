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

def classify_fast(user_msg: str) -> dict | None:
    """Pattern-based classification. No LLM needed."""
    msg = user_msg.lower().strip()
    
    # ── URL DETECTION (highest priority) ──────────────────
    url_patterns = [
        r'https?://[^\s]+',                    # Full URL
        r'[a-zA-Z0-9-]+\.[a-zA-Z]{2,}',       # domain.com style
        r'[a-zA-Z0-9-]+\.vercel\.app',         # Vercel apps
        r'[a-zA-Z0-9-]+\.netlify\.app',        # Netlify apps
        r'[a-zA-Z0-9-]+\.github\.io',          # GitHub pages
    ]
    
    has_url = any(re.search(p, user_msg) for p in url_patterns)
    
    # Check for browse intent words
    browse_words = ["go to", "check out", "visit", "open", "browse",
                    "look at", "read", "what does", "tell me about", "access", "blog"]
    has_browse_intent = any(w in msg for w in browse_words) or "blog" in msg
    
    if has_url or has_browse_intent:
        # If it's just "access my blogs" without a URL, 
        # the handler should attempt to find it in context.
        return {
            "thought": "URL or browse/blog intent detected",
            "tier": "agentic",
            "action": "web_browse",
            "requires_tools": True,
            "complexity": "low",
        }
    
    # ── SEARCH DETECTION ──────────────────────────────────
    search_starters = [
        "search for", "search about", "look up", "find me",
        "google", "what is the latest", "latest news",
        "find information", "research",
    ]
    if any(msg.startswith(s) or s in msg for s in search_starters):
        return {
            "thought": "Search intent detected",
            "tier": "agentic",
            "action": "search",
            "requires_tools": True,
            "complexity": "low",
        }
    
    # ── SOCIAL (existing) ─────────────────────────────────
    social_words = {"hi","hello","hey","yo","sup","hy","heyy",
                    "wbu","hru","gm","gn","thx","thanks","ok",
                    "cool","lol","bye"}
    if msg in social_words or len(msg.split()) <= 2 or "yo what is up" in msg:
        return {
            "thought": "Social greeting",
            "tier": "fast",
            "action": "social",
            "requires_tools": False,
            "complexity": "low",
        }
    
    # ── INTERNAL QUERY (existing) ─────────────────────────
    internal_kw = ["my tasks", "my reminders", "scheduled",
                   "my memory", "know about me", "my jobs", "remind"]
    if any(kw in msg for kw in internal_kw):
        tier = "scheduled" if "remind" in msg else "fast"
        return {
            "thought": "Internal data request" if tier == "fast" else "Scheduled task request",
            "tier": tier,
            "action": "internal_query" if tier == "fast" else "reminder",
            "requires_tools": False,
            "complexity": "low",
        }
    
    return None  # Needs LLM classification


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
    """
    Rule-based fallback when LLM classifier fails.
    NEVER default to complex. Analyze the message.
    """
    msg = user_msg.lower().strip()
    
    # Try pattern matching first
    pattern_result = classify_fast(user_msg)
    if pattern_result:
        pattern_result["thought"] = "Fallback: pattern match after LLM failure"
        # Ensure semantic consistency with _validate_intent's output
        pattern_result["complexity_hint"] = "simple" if pattern_result["tier"] == "fast" else "complex"
        pattern_result["urgency"] = "normal"
        pattern_result["entities"] = []
        pattern_result["skill_name"] = ""
        return pattern_result
    
    # Length-based heuristic
    word_count = len(msg.split())
    
    if word_count <= 3:
        return {
            "thought": "Fallback: short message, likely social or simple",
            "tier": "fast",
            "action": "social",
            "requires_tools": False,
            "complexity": "low",
            "complexity_hint": "simple",
            "urgency": "normal",
            "entities": [],
            "skill_name": ""
        }
    
    if word_count <= 10:
        return {
            "thought": "Fallback: medium message, treating as general query",
            "tier": "fast",
            "action": "other",
            "requires_tools": False,
            "complexity": "low",
            "complexity_hint": "simple",
            "urgency": "normal",
            "entities": [],
            "skill_name": ""
        }
    
    # Longer messages are more likely to need agentic handling
    return {
        "thought": "Fallback: longer message, treating as agentic",
        "tier": "agentic",
        "action": "other",
        "requires_tools": False,
        "complexity": "medium",
        "complexity_hint": "complex",
        "urgency": "normal",
        "entities": [],
        "skill_name": ""
    }


async def parse_intent(prompt: str) -> dict:
    """
    Call the LLM (lightweight tier) to parse user intent.
    Checks fast patterns first to save tokens.
    """
    from src.llm.gateway import complete

    # 1. Fast Pattern Path
    fast_result = classify_fast(prompt)
    if fast_result:
        logger.info("✅ PATTERN MATCH: %s (%s/%s)", prompt, fast_result['tier'], fast_result['action'])
        # Add required defaults for downstream systems
        fast_result.setdefault("complexity_hint", "simple" if fast_result["tier"] == "fast" else "complex")
        fast_result.setdefault("urgency", "normal")
        fast_result.setdefault("entities", [])
        fast_result.setdefault("skill_name", "")
        return fast_result

    logger.info("🔍 CLASSIFYING: %s", prompt)
    sys_prompt = get_dynamic_system_prompt()
    
    try:
        result = await complete(
            prompt=prompt,
            model_tier="lightweight",
            system_prompt=sys_prompt,
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

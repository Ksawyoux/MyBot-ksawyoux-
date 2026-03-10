"""
src/router/intent_parser.py — Extract intent, urgency, and entities from user input
"""

import json
from src.utils.logging import get_logger

logger = get_logger(__name__)

INTENT_SYSTEM_PROMPT = """
You are a categorization engine for an AI assistant. You do not converse. You only output JSON.
Analyze the user's message and determine the intent.
Return ONLY a valid JSON object matching this schema:
{
  "action": "question|email|calendar|search|schedule|other",
  "urgency": "high|normal|low",
  "entities": ["list", "of", "key", "entities"],
  "complexity_hint": "simple|complex"
}

RULES:
1. If the user says "Who are you?", "What can you do?", "Hi" -> {"action": "question", "urgency": "normal", "entities": [], "complexity_hint": "simple"}
2. Any action requiring email/calendar/search MUST be "complex".
3. Any scheduled recurring action MUST be "schedule".
4. You MUST NOT answer the user's question. ONLY classify it.

EXAMPLES:
User: "What's the weather in Tokyo?"
{"action": "search", "urgency": "normal", "entities": ["Tokyo", "weather"], "complexity_hint": "complex"}

User: "Schedule a sync for tomorrow."
{"action": "calendar", "urgency": "normal", "entities": ["sync", "tomorrow"], "complexity_hint": "complex"}

User: "Who are you?"
{"action": "question", "urgency": "normal", "entities": [], "complexity_hint": "simple"}

YOUR OUTPUT MUST BE ONLY THE JSON OBJECT.
"""


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
                    if "name" in parsed:
                        skills.append(f"- {parsed['name']}: {parsed['description']}")
        
        if skills:
            skills_context = "\n\nInstalled Skills available for action='skill':\n" + "\n".join(skills)
            
    base_prompt = INTENT_SYSTEM_PROMPT
    if skills_context:
        base_prompt = base_prompt.replace(
            '"action": "question|email|calendar|search|schedule|other"',
            '"action": "question|email|calendar|search|schedule|skill|other",\n  "skill_name": "name of skill if action is skill (from list below)"'
        )
        base_prompt += skills_context
        
    return base_prompt


async def parse_intent(prompt: str) -> dict:
    """
    Call the LLM (lightweight tier) to parse user intent.
    Returns a dict with action, urgency, entities, and complexity_hint.
    """
    from src.llm.gateway import complete

    try:
        result = await complete(
            prompt=prompt,
            model_tier="lightweight",
            system_prompt=get_dynamic_system_prompt(),
            use_cache=True,
        )

        response = result["response"].strip()

        # Clean markdown formatting if model misbehaves
        if response.startswith("```json"):
            response = response[7:]
        if response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]

        parsed = json.loads(response.strip())
        
        # Ensure default fields
        parsed.setdefault("action", "other")
        parsed.setdefault("urgency", "normal")
        parsed.setdefault("entities", [])
        parsed.setdefault("complexity_hint", "complex")
        parsed.setdefault("skill_name", "")

        logger.debug("Parsed intent: action=%s, skill=%s, complexity=%s", 
                     parsed["action"], parsed["skill_name"], parsed["complexity_hint"])
        return parsed

    except json.JSONDecodeError as e:
        logger.warning("Intent parser returned invalid JSON. Error: %s. Raw response: %s. Defaulting to 'complex/other'.", e, result.get("response", ""))
        return {
            "action": "other",
            "urgency": "normal",
            "entities": [],
            "complexity_hint": "complex",
        }
    except Exception as exc:
        logger.error("Intent parsing failed: %s", exc)
        return {
            "action": "other",
            "urgency": "normal",
            "entities": [],
            "complexity_hint": "complex",
        }

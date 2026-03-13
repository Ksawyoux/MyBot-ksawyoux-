"""
src/router/intent_parser.py — Extract intent, urgency, and entities from user input
"""

import json
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
            response_format={"type": "json_object"}
        )

        response = result["response"]
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

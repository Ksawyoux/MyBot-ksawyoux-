"""
src/agents/skill_loader.py — Parses claude-skills markdown and creates CrewAI agents
"""

import os
import re
from crewai import Agent, Task
from src.utils.logging import get_logger

logger = get_logger(__name__)


def parse_skill_markdown(file_path: str) -> dict:
    """
    Parses a SKILL.md file with YAML frontmatter.
    Returns a dictionary with 'name', 'description' and 'body'.
    """
    if not os.path.exists(file_path):
        return {}
    
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Match YAML frontmatter (\A matches start of string)
    pattern = r"\A---\s*\n(.*?)\n---\s*\n(.*)"
    match = re.search(pattern, content, re.DOTALL)
    
    if not match:
        logger.warning(f"Could not parse frontmatter for {file_path}")
        return {"name": os.path.basename(os.path.dirname(file_path)), "description": "", "body": content[:1000]}
    
    frontmatter = match.group(1)
    body = match.group(2)
    
    # Parse simple key-value pairs in frontmatter
    meta = {}
    for line in frontmatter.split("\n"):
        if ":" in line:
            key, val = line.split(":", 1)
            key = key.strip()
            val = val.strip().strip("'\"")
            meta[key] = val
            
    return {
        "name": meta.get("name", "Unknown Skill"),
        "description": meta.get("description", ""),
        "body": body
    }


def create_skill_agent(skill_name: str, llm) -> Agent:
    """Create a CrewAI Agent based on a SKILL.md file."""
    skills_dir = os.path.join(os.path.dirname(__file__), "..", "skills")
    skill_path = os.path.join(skills_dir, skill_name)
    skill_file = os.path.join(skill_path, "SKILL.md")
    
    parsed = parse_skill_markdown(skill_file)
    
    role = parsed.get("name", skill_name).replace("-", " ").title()
    goal = parsed.get("description", "Execute the specific skill instructions.")
    backstory_content = parsed.get("body", "")
    
    return Agent(
        role=role,
        goal=goal,
        backstory=f"You are a specialized agent following these exact instructions:\n\n{backstory_content}",
        verbose=True,
        allow_delegation=False,
        llm=llm
    )


def create_skill_task(agent: Agent, instruction: str) -> Task:
    return Task(
        description=instruction,
        expected_output="A comprehensive response fulfilling the user's request based on your specific skills, OR a confirmation that a required action was sent to the human approval queue.",
        agent=agent
    )

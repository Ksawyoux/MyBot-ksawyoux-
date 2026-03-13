"""
src/agents/briefing_agent.py — CrewAI configuration for the Morning Briefing Agent
"""

from crewai import Agent, Task
import datetime

def create_briefing_agent(llm) -> Agent:
    """Create the Morning Briefing Agent."""
    return Agent(
        role="Executive Chief of Staff",
        goal="Synthesize the user's unread emails, today's calendar events, and relevant memories into a concise, highly actionable morning digest.",
        backstory="You are a proactive, world-class Chief of Staff. You anticipate the user's needs by analyzing their schedule and identifying critical emails requiring their attention. You never overwhelm them with raw data; instead, you provide strategic summaries.",
        verbose=True,
        allow_delegation=False,
        llm=llm
    )

def create_briefing_task(agent: Agent, prompt: str) -> Task:
    """Create the daily briefing task."""
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    
    full_instruction = (
        f"Today is {today}. Your task is to generate a 'Morning Digest' for the user.\n\n"
        "STEPS:\n"
        "1. Check the user's calendar for events happening today.\n"
        "2. Check the user's recent unread emails.\n"
        "3. Synthesize this data along with the user preferences provided below into a beautiful, markdown-formatted Morning Briefing.\n"
        "4. Flag any 'heavy' days (e.g., back-to-back meetings) or high-priority emails that need immediate replies.\n\n"
        f"USER CONTEXT & PREFERENCES:\n{prompt}\n\n"
        "EXPECTED OUTPUT:\n"
        "A highly readable markdown digest containing:\n"
        "- A brief 1-2 sentence executive summary of the day.\n"
        "- A bulleted list of today's schedule (with times).\n"
        "- A summary of 1-3 critical unread emails (if any).\n"
        "- A proactive suggestion (e.g., 'You have 4 hours of meetings today, remember to take a break.')."
    )
    
    return Task(
        description=full_instruction,
        expected_output="A polished, markdown-formatted Morning Digest summarizing today's schedule, key emails, and a proactive suggestion.",
        agent=agent
    )

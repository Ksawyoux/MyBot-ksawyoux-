"""
src/agents/calendar_agent.py — CrewAI configuration for the calendar manager
"""

from crewai import Agent, Task
from src.utils.logging import get_logger

logger = get_logger(__name__)


def create_calendar_agent(llm) -> Agent:
    """Create the Calendar Manager Agent."""
    return Agent(
        role="Calendar Coordinator",
        goal="Manage the user's schedule, find open slots, and create calendar events.",
        backstory="You are a strict time manager. You ensure the user's schedule is balanced "
                  "and that all appointments are accurately recorded in their calendar.",
        verbose=True,
        allow_delegation=False,
        llm=llm
    )


def create_calendar_task(agent: Agent, instruction: str) -> Task:
    return Task(
        description=instruction,
        expected_output="Confirmation of calendar events retrieved or scheduled, OR a confirmation that the action was sent to the human approval queue.",
        agent=agent
    )

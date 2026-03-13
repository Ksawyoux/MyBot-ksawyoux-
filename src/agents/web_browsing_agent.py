"""
src/agents/web_browsing_agent.py — Specialized agent for complex web interaction tasks.
"""

from crewai import Agent, Task
from src.utils.logging import get_logger

logger = get_logger(__name__)

def create_web_agent(llm) -> Agent:
    """
    Creates an autonomous web browsing agent that can navigate, observe, and interact.
    """
    return Agent(
        role="Web Systems Automation Specialist",
        goal="Navigate websites, interact with UI elements (clicks, types), and extract structured information to solve complex user requests.",
        backstory=(
            "You are a master of web systems automation. You don't just read pages; you interact with them. "
            "You know how to use 'web_list_elements' to see what's on a page, 'web_click' to navigate or submit forms, "
            "and 'web_type' to provide input. You are persistent, methodical, and can handle dynamic modern web apps (SPAs)."
        ),
        llm=llm,
        verbose=True,
        allow_delegation=False,
        memory=True
    )

def create_web_task(agent: Agent, prompt: str) -> Task:
    """
    Creates a task for the web browsing agent.
    """
    return Task(
        description=(
            f"Fulfill the following user request by interacting with the web: {prompt}\n\n"
            "Execution Strategy:\n"
            "1. Start by navigating to the relevant URL using 'browse_url'.\n"
            "2. If entry points aren't obvious, use 'web_list_elements' to identify buttons or links.\n"
            "3. Use 'web_click' to navigate deeper or 'web_type' if searching/inputting data is required.\n"
            "4. Always confirm the state of the page after an interaction by checking the output 'content_preview'.\n"
            "5. Repeat until you have reached the goal or extracted all necessary information."
        ),
        expected_output="A comprehensive report on the actions performed and the final result or information retrieved.",
        agent=agent
    )

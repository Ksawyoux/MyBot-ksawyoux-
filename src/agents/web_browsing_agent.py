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
        role="Web Browsing Specialist",
        goal="Navigate websites, extract information, and interact with web elements to solve complex tasks.",
        backstory=(
            "You are an expert at navigating the modern web. You understand how to use browsers, "
            "identify key information on JS-heavy sites, and interact with forms and buttons. "
            "You are persistent and can handle cookie banners, popups, and complex layouts."
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
            f"Solve the following web-related task: {prompt}\n\n"
            "Steps to follow:\n"
            "1. Analyze the requirement and identify the target URL(s).\n"
            "2. Use the 'browse_url' tool to fetch the initial content.\n"
            "3. If the page is interactive or dynamic, use 'click_element' or 'fill_form' as needed.\n"
            "4. Extract the requested information or perform the requested action.\n"
            "5. Synthesize your findings and provide a final answer."
        ),
        expected_output="A detailed summary of findings or confirmation of actions performed on the web.",
        agent=agent
    )

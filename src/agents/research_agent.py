"""
src/agents/research_agent.py — CrewAI configuration for the web researcher
"""

from crewai import Agent, Task
from src.utils.logging import get_logger

logger = get_logger(__name__)


def create_research_agent(llm) -> Agent:
    """Create the Web Researcher Agent."""
    return Agent(
        role="Senior Web Researcher",
        goal="Find accurate, up-to-date information on the web and synthesize it clearly.",
        backstory="You are an expert researcher capable of using search engines and reading webpages "
                  "to extract the exact information required.",
        verbose=True,
        allow_delegation=False,
        llm=llm
    )


def create_research_task(agent: Agent, instruction: str) -> Task:
    return Task(
        description=instruction,
        expected_output="A comprehensive, factual report fulfilling the research objective, OR a confirmation that a required action was sent to the human approval queue.",
        agent=agent
    )

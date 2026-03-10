"""
src/agents/email_agent.py — CrewAI configuration for the email assistant
"""

import yaml
from crewai import Agent, Task
from src.mcp.client import get_mcp_client
from src.utils.logging import get_logger

logger = get_logger(__name__)


def create_email_agent(llm) -> Agent:
    """Create the Email Assistant Agent."""
    mcp_client = get_mcp_client()
    
    # In CrewAI, we pass a list of tools. We'll wrap our MCP tools into standard 
    # Langchain/CrewAI Tool objects in the crew manager. For config, we just define the agent.
    return Agent(
        role="Executive Email Assistant",
        goal="Read, filter, draft, and manage emails efficiently while adhering to user preferences.",
        backstory="You are a meticulous executive assistant who manages the user's inbox "
                  "and ensures no important communication is missed.",
        verbose=True,
        allow_delegation=False,
        llm=llm
    )


def create_email_task(agent: Agent, instruction: str) -> Task:
    """Create a generic task for the email agent."""
    return Task(
        description=instruction,
        expected_output="A clear summary of actions taken, emails read, drafts prepared, OR a confirmation that the action was sent to the human approval queue.",
        agent=agent
    )

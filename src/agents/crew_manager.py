"""
src/agents/crew_manager.py — Orchestrates CrewAI agents and tools
"""

from typing import Any
from crewai import Crew, Process
from langchain_core.tools import Tool
from pydantic import BaseModel, Field

from src.mcp.client import get_mcp_client
from src.approval.gateway import wrap_tool_execution
from src.utils.logging import get_logger

logger = get_logger(__name__)


def _create_langchain_tools(task_id: int) -> list[Tool]:
    """
    Wrap our MCP tools in LangChain Tool objects so CrewAI can use them.
    We inject the `task_id` so the Approval Gateway knows which task triggered it.
    """
    mcp_client = get_mcp_client()
    lc_tools = []

    for name, meta in mcp_client._tools.items():
        # Capture the current name in the closure
        def make_tool(tool_name=name):
            async def _run_tool(**kwargs):
                logger.debug("CrewAI Agent calling tool: %s", tool_name)
                # Pass through the Approval Gateway
                return await wrap_tool_execution(tool_name, kwargs, task_id)
            return _run_tool

        lc_tools.append(
            Tool(
                name=name,
                func=make_tool(),
                description=meta["description"]
            )
        )
    return lc_tools


# Define a lightweight LLM wrapper for CrewAI using our gateway
# CrewAI expects an LLM object with a `call` or `bind_tools` interface,
# usually from langchain. We will use Langchain's ChatOpenAI but point it at OpenRouter.

def _get_crewai_llm(model_tier: str = "balanced"):
    from langchain_openai import ChatOpenAI
    from src.config.settings import OPENROUTER_API_KEY
    from src.config.models import MODEL_TIERS
    
    tier_config = MODEL_TIERS[model_tier]
    
    return ChatOpenAI(
        model=f"openrouter/{tier_config['primary']}",
        api_key=OPENROUTER_API_KEY,
        base_url="https://openrouter.ai/api/v1",
        max_tokens=tier_config["max_tokens"],
        # Add headers required by OpenRouter
        default_headers={
            "HTTP-Referer": "https://github.com/Ksawyoux",
            "X-Title": "Atlasia AI Agent",
        }
    )


async def execute_crew_task(intent: dict, prompt: str, task_id: int) -> str:
    """
    Assemble the right crew based on the extracted intent and execute the task.
    """
    from src.agents.email_agent import create_email_agent, create_email_task
    from src.agents.research_agent import create_research_agent, create_research_task
    from src.agents.calendar_agent import create_calendar_agent, create_calendar_task

    action = intent.get("action", "other")
    llm = _get_crewai_llm("capable") # Deep reasoning
    tools = _create_langchain_tools(task_id)

    agents = []
    tasks = []

    # Map intent to agents
    if action == "skill":
        from src.agents.skill_loader import create_skill_agent, create_skill_task
        skill_name = intent.get("skill_name", "")
        if skill_name:
            agent = create_skill_agent(skill_name, llm)
            agent.tools = tools
            agents.append(agent)
            tasks.append(create_skill_task(agent, prompt))
        else:
            logger.warning("Action is 'skill' but 'skill_name' is empty. Fallback to 'other'.")
            action = "other"  # let the 'else' block handle it below

    # Check again in case it fell back
    if action == "email":
        agent = create_email_agent(llm)
        agent.tools = tools
        agents.append(agent)
        tasks.append(create_email_task(agent, prompt))
        
    elif action == "calendar":
        agent = create_calendar_agent(llm)
        agent.tools = tools
        agents.append(agent)
        tasks.append(create_calendar_task(agent, prompt))
        
    elif action == "search":
        agent = create_research_agent(llm)
        agent.tools = tools
        agents.append(agent)
        tasks.append(create_research_task(agent, prompt))
        
    else:
        # Default: general research and assistant
        agent1 = create_research_agent(llm)
        agent1.tools = tools
        agents.append(agent1)
        tasks.append(create_research_task(agent1, "Research context for: " + prompt))
        
        # If it's a general complex task, might need email too
        if "email" in intent.get("entities", []):
            agent2 = create_email_agent(llm)
            agent2.tools = tools
            agents.append(agent2)
            tasks.append(create_email_task(agent2, "Draft communication based on research regarding: " + prompt))

    logger.info("Assembled crew with %d agents for action '%s'", len(agents), action)

    crew = Crew(
        agents=agents,
        tasks=tasks,
        process=Process.sequential,
        verbose=True
    )

    # CrewAI execute (blocking, but we'll run it in a thread later if needed)
    try:
        # CrewAI kickoff is synchronous, we use asyncio.to_thread to not block the event loop
        import asyncio
        result = await asyncio.to_thread(crew.kickoff)
        return str(result)
    except Exception as exc:
        logger.error("Crew execution failed: %s", exc)
        return f"Crew encountered an error: {str(exc)}"

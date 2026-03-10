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


from crewai.tools import BaseTool

def _create_langchain_tools(task_id: int) -> list[BaseTool]:
    """
    Wrap our MCP tools in CrewAI BaseTool objects.
    """
    mcp_client = get_mcp_client()
    tools = mcp_client._tools
    logger.info("CrewAI loading %d registered MCP tools.", len(tools))
    
    lc_tools = []

    for name, meta in tools.items():
        # Build Pydantic args_schema manually from JSON Schema parameters
        from pydantic import create_model
        from typing import Optional
        fields = {}
        schema = meta.get("parameters", {})
        properties = schema.get("properties", {})
        required_fields = schema.get("required", [])
        
        for prop_name, prop_info in properties.items():
            prop_type_str = prop_info.get("type", "string")
            type_mapping = {
                "string": str,
                "integer": int,
                "number": float,
                "boolean": bool,
                "array": list,
                "object": dict
            }
            prop_type = type_mapping.get(prop_type_str, Any)
            description = prop_info.get("description", "")
            
            if prop_name in required_fields:
                fields[prop_name] = (prop_type, Field(..., description=description))
            else:
                opt_type = Optional[prop_type]
                default_val = prop_info.get("default", None)
                fields[prop_name] = (opt_type, Field(default_val, description=description))
                
        # Must be careful not to reuse the same class name incorrectly, use a unique name
        tool_schema_name = "".join(part.capitalize() for part in name.split("_")) + "Schema"
        SchemaClass = create_model(tool_schema_name, **fields)

        # Define a dynamic class to satisfy CrewAI's requirement for BaseTool subclasses
        # We must use a unique class name or just subclass locally
        custom_tool_name = "".join(part.capitalize() for part in name.split("_")) + "Tool"
        
        class MCPWrappedTool(BaseTool):
            args_schema: type[BaseModel] = SchemaClass

            def _run(self, **kwargs: Any) -> Any:
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                
                if loop.is_running():
                    import nest_asyncio
                    nest_asyncio.apply()
                
                # We can access `self.name` because it is set by BaseTool __init__
                result = asyncio.run(wrap_tool_execution(self.name, kwargs, task_id))
                
                if isinstance(result, dict) and result.get("status") == "pending_approval":
                    return (
                        f"Action '{self.name}' has been intercepted and requires human approval. "
                        f"Approval ID: {result.get('approval_id')}. "
                        "Do NOT retry this action. "
                        "Please provide your Final Answer confirming that the action has been submitted for approval."
                    )
                import json
                return json.dumps(result) if isinstance(result, dict) else str(result)
        
        # Override the __name__ to be unique
        MCPWrappedTool.__name__ = custom_tool_name

        lc_tools.append(MCPWrappedTool(name=name, description=meta["description"]))
        
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

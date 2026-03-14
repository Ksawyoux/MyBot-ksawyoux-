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

# Cache of already-built tool classes keyed by tool name.
# Avoids rebuilding Pydantic models + dynamic classes on every crew execution.
_tool_class_cache: dict[str, BaseTool] = {}


def _build_tool_class(name: str, meta: dict) -> type[BaseTool]:
    """
    Build (once) a CrewAI BaseTool subclass for a single MCP tool.
    task_id is stored as an instance attribute set at instantiation time.
    """
    from pydantic import create_model
    from typing import Optional

    schema = meta.get("parameters", {})
    properties = schema.get("properties", {})
    required_fields = schema.get("required", [])

    _type_map = {
        "string": str, "integer": int, "number": float,
        "boolean": bool, "array": list, "object": dict,
    }
    fields: dict = {}
    for prop_name, prop_info in properties.items():
        prop_type = _type_map.get(prop_info.get("type", "string"), Any)
        desc = prop_info.get("description", "")
        if prop_name in required_fields:
            fields[prop_name] = (prop_type, Field(..., description=desc))
        else:
            fields[prop_name] = (Optional[prop_type], Field(prop_info.get("default"), description=desc))

    schema_cls_name = "".join(p.capitalize() for p in name.split("_")) + "Schema"
    SchemaClass = create_model(schema_cls_name, **fields)

    class MCPWrappedTool(BaseTool):
        args_schema: type[BaseModel] = SchemaClass
        # task_id is set on the instance after construction
        _task_id: int = 0

        def _run(self, **kwargs: Any) -> Any:
            import asyncio
            import json

            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            if loop.is_running():
                import nest_asyncio
                nest_asyncio.apply()

            result = asyncio.run(wrap_tool_execution(self.name, kwargs, self._task_id))

            if isinstance(result, dict) and result.get("status") == "pending_approval":
                return (
                    f"Action '{self.name}' has been intercepted and requires human approval. "
                    f"Approval ID: {result.get('approval_id')}. "
                    "Do NOT retry this action. "
                    "Please provide your Final Answer confirming that the action has been submitted for approval."
                )
            return json.dumps(result) if isinstance(result, dict) else str(result)

    tool_class_name = "".join(p.capitalize() for p in name.split("_")) + "Tool"
    MCPWrappedTool.__name__ = tool_class_name
    return MCPWrappedTool


def _create_langchain_tools(task_id: int) -> list[BaseTool]:
    """
    Wrap MCP tools as CrewAI BaseTool objects.
    Tool classes are built once and cached; task_id is stamped on each fresh instance.
    """
    mcp_client = get_mcp_client()
    tools = mcp_client._tools
    logger.info("CrewAI loading %d registered MCP tools.", len(tools))

    lc_tools = []
    for name, meta in tools.items():
        if name not in _tool_class_cache:
            _tool_class_cache[name] = _build_tool_class(name, meta)
        tool_cls = _tool_class_cache[name]
        instance = tool_cls(name=name, description=meta["description"])
        instance._task_id = task_id
        lc_tools.append(instance)

    return lc_tools





# Define a lightweight LLM wrapper for CrewAI using our gateway
# CrewAI expects an LLM object with a `call` or `bind_tools` interface,
# usually from langchain. We will use Langchain's ChatOpenAI but point it at OpenRouter.

def _get_crewai_llm(model_tier: str = "balanced"):
    from langchain_openai import ChatOpenAI
    from src.config.settings import OPENAI_API_KEY, OPENAI_BASE_URL
    from src.config.models import MODEL_TIERS
    
    tier_config = MODEL_TIERS[model_tier]
    
    return ChatOpenAI(
        model=tier_config['primary'],
        api_key=OPENAI_API_KEY,
        base_url=OPENAI_BASE_URL,
        max_tokens=tier_config["max_tokens"],
    )


async def execute_crew_task(intent: dict, prompt: str, task_id: int) -> str:
    """
    Assemble the right crew based on the extracted intent and execute the task.
    """
    from src.agents.email_agent import create_email_agent, create_email_task
    from src.agents.research_agent import create_research_agent, create_research_task
    from src.agents.calendar_agent import create_calendar_agent, create_calendar_task
    from src.agents.web_browsing_agent import create_web_agent, create_web_task

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
        
    elif action == "briefing":
        from src.agents.briefing_agent import create_briefing_agent, create_briefing_task
        agent = create_briefing_agent(llm)
        agent.tools = tools
        agents.append(agent)
        tasks.append(create_briefing_task(agent, prompt))
        
    elif action == "web_browse":
        agent = create_web_agent(llm)
        agent.tools = tools
        agents.append(agent)
        tasks.append(create_web_task(agent, prompt))
        
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
        if not result:
            raise ValueError("CrewAI returned empty response")
        return str(result)
    except Exception as exc:
        logger.error("Crew execution failed: %s", exc, exc_info=True)
        logger.warning("Falling back to standard LLM completion due to CrewAI failure.")
        from src.llm.gateway import complete
        fallback_result = await complete(
            prompt="Attempted to complete this complex task but the automated crew failed. "
                   "Please do your best to answer this based on your own knowledge: " + prompt,
            model_tier="capable",
            system_prompt="You are a helpful AI assistant.",
            priority=0
        )
        return fallback_result["response"]

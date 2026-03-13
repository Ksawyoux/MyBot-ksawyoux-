"""
src/mcp/client.py — Simple Model Context Protocol Client
"""

from typing import Any, Optional
from src.utils.logging import get_logger

logger = get_logger(__name__)


class MCPClient:
    """
    Executes tool calls by interacting with registered MCP servers.
    In Phase 4, we embed the Python servers directly instead of running them 
    over stdio to save memory on Render's free tier.
    """

    def __init__(self):
        self._tools: dict = {}

    def register_tool(self, name: str, func, description: str, parameters: dict) -> None:
        """Register a tool exposed by an MCP server."""
        self._tools[name] = {
            "func": func,
            "description": description,
            "parameters": parameters,
        }
        logger.debug("Registered MCP tool: %s", name)

    def list_tools(self) -> list[dict]:
        """Return tools formatted for LLM function calling schemas."""
        output = []
        for name, meta in self._tools.items():
            output.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": meta["description"],
                    "parameters": meta["parameters"]
                }
            })
        return output

    def get_connected_servers(self) -> list[str]:
        """In Phase 4, servers are embedded. We infer names from register calls."""
        # Simple heuristic: scrape, email, calendar, brave-search, github, filesystem
        # In a real system, we'd track this during registration.
        servers = set()
        for tool in self._tools.keys():
            if "email" in tool: servers.add("google-tools")
            elif "calendar" in tool: servers.add("google-calendar")
            elif "search" in tool: servers.add("web-search")
            elif "github" in tool: servers.add("github")
            elif "file" in tool: servers.add("filesystem")
            elif "fetch" in tool or "browse" in tool or "click" in tool or "fill" in tool: servers.add("web-fetch")
        return list(servers)

    def get_tool_meta(self, name: str) -> Optional[dict]:
        return self._tools.get(name)

    async def call_tool(self, name: str, kwargs: dict) -> Any:
        """Execute a tool. (Phase 5 will wrap this in an approval check)."""
        if name not in self._tools:
            logger.error("Attempted to call unknown tool: %s", name)
            return {"error": f"Tool '{name}' not found."}

        logger.info("Executing tool: %s", name)
        try:
            func = self._tools[name]["func"]
            # If the tool is async, await it
            import inspect
            if inspect.iscoroutinefunction(func):
                result = await func(**kwargs)
            else:
                result = func(**kwargs)
            return result
        except Exception as exc:
            logger.error("Tool '%s' failed: %s", name, exc)
            return {"error": str(exc)}


# Module-level singleton
_mcp_client = MCPClient()


def get_mcp_client() -> MCPClient:
    return _mcp_client

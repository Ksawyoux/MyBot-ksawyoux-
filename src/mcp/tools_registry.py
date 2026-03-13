"""
src/mcp/tools_registry.py — Initialize all MCP tools
"""

from src.mcp.servers.scraper_server import register_scraper_tools
from src.mcp.servers.email_server import register_email_tools
from src.mcp.servers.calendar_server import register_calendar_tools
from src.tools.web_tools import register_web_tools
from src.mcp.client import get_mcp_client
from src.utils.logging import get_logger

logger = get_logger(__name__)


def init_tools() -> None:
    """Register all available tools with the MCP Client."""
    logger.info("Registering MCP tools...")
    register_scraper_tools()
    register_email_tools()
    register_calendar_tools()
    register_web_tools()
    
    client = get_mcp_client()
    tools = client.list_tools()
    logger.info("Registered %d tools across all MCP servers.", len(tools))

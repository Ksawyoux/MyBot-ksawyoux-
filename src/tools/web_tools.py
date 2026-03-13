from typing import Dict, Any
from src.mcp.client import get_mcp_client
from src.tools.web_search import search_tool, format_results_for_llm
from src.tools.web_fetch import fetch_url as fetch_url_internal
from src.tools.web_cache import web_cache

async def browse_url(url: str) -> Dict[str, Any]:
    """Fetches content from a URL using web_fetch."""
    return await fetch_url_internal(url)

async def web_search_tool(query: str) -> Dict[str, Any]:
    """Performs a web search using web_search."""
    results = await search_tool.web_search(query)
    return {
        "results": results,
        "formatted": format_results_for_llm(results)
    }

def register_web_tools():
    """Registers web tools with the global MCP client."""
    client = get_mcp_client()
    
    client.register_tool(
        name="web_fetch",
        func=browse_url,
        description="Fetch content from a URL and extract clean text.",
        parameters={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The URL to fetch"}
            },
            "required": ["url"]
        }
    )

    client.register_tool(
        name="web_search",
        func=web_search_tool,
        description="Search the web for a query using DuckDuckGo.",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query"}
            },
            "required": ["query"]
        }
    )

    from src.tools.web_interact import get_interactive_elements, click_element, type_text

    client.register_tool(
        name="web_list_elements",
        func=get_interactive_elements,
        description="List interactive elements (buttons, links) on a page to decide what to click.",
        parameters={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The URL to analyze"}
            },
            "required": ["url"]
        }
    )

    client.register_tool(
        name="web_click",
        func=click_element,
        description="Click an element on a web page using a selector.",
        parameters={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The current page URL"},
                "selector": {"type": "string", "description": "CSS selector to click"}
            },
            "required": ["url", "selector"]
        }
    )

    client.register_tool(
        name="web_type",
        func=type_text,
        description="Type text into an input field on a web page.",
        parameters={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The current page URL"},
                "selector": {"type": "string", "description": "CSS selector for the input"},
                "text": {"type": "string", "description": "The text to type"},
                "press_enter": {"type": "boolean", "description": "Whether to press Enter after typing", "default": True}
            },
            "required": ["url", "selector", "text"]
        }
    )

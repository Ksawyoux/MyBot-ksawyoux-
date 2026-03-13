"""
src/tools/web_tools.py — MCP Tool definitions for web browsing.
"""

from typing import Dict, Any, Optional
from src.mcp.client import get_mcp_client
from src.utils.logging import get_logger
from src.skills.web_interaction.strategy import select_browsing_strategy, get_fallback_strategy
from src.skills.web_interaction.scraper import fetch_page
from src.skills.web_interaction.browser import browse_url_dynamic, perform_action
from src.skills.web_interaction.cache import get_from_cache, set_in_cache
from src.skills.web_interaction.safety import requires_approval, is_url_safe

import os
import httpx
from bs4 import BeautifulSoup

logger = get_logger(__name__)

async def browse_url(url: str) -> Dict[str, Any]:
    """
    Fetches content from a URL using the best available strategy.
    """
    # 1. Check Cache
    cached = get_from_cache(url)
    if cached:
        return cached

    # 2. Select Strategy
    strategy = select_browsing_strategy(url)
    
    # 3. Execute
    result = None
    if strategy == "scraper":
        result = await fetch_page(url)
        if "error" in result:
            fallback = get_fallback_strategy("scraper")
            if fallback == "browser":
                result = await browse_url_dynamic(url)
    else:
        result = await browse_url_dynamic(url)

    # 4. Cache and Return
    if "error" not in result:
        set_in_cache(url, result)
    
    return result

async def click_element(selector: str) -> Dict[str, Any]:
    """Clicks an element on the current page."""
    return await perform_action("click", {"selector": selector})

async def fill_form(selector: str, value: str) -> Dict[str, Any]:
    """Fills a form field on the current page."""
    return await perform_action("fill", {"selector": selector, "value": value})

async def web_search(query: str) -> Dict[str, Any]:
    """
    Performs a web search using a public search engine (DuckDuckGo fallback).
    """
    logger.info("Performing web search for: %s", query)
    
    # Check if Brave API Key exists (Phase 5 improvement)
    brave_key = os.getenv("BRAVE_API_KEY")
    if brave_key:
        # Implementation for Brave API would go here
        pass

    # Fallback: DuckDuckGo scraping (or using a public search API)
    # Note: Scraping search engines can be brittle, but works for a direct "no-setup" experience.
    search_url = f"https://duckduckgo.com/html/?q={query}"
    result = await fetch_page(search_url)
    
    if "error" in result:
        return result

    soup = BeautifulSoup(result["html"], "html.parser")
    links = []
    for result in soup.find_all("a", class_="result__a")[:5]:
        links.append({
            "title": result.get_text(),
            "url": result["href"]
        })
        
    return {
        "query": query,
        "results": links,
        "source": "DuckDuckGo (Free Fallback)"
    }

def register_web_tools():
    """Registers web tools with the global MCP client."""
    client = get_mcp_client()
    
    client.register_tool(
        name="browse_url",
        func=browse_url,
        description="Fetch content from a URL. Automatically chooses between static scraping and dynamic browsing.",
        parameters={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The URL to browse"}
            },
            "required": ["url"]
        }
    )

    client.register_tool(
        name="click_element",
        func=click_element,
        description="Click an element (link, button) on the currently open page using a CSS selector or ID.",
        parameters={
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "CSS selector or ID of the element"}
            },
            "required": ["selector"]
        }
    )

    client.register_tool(
        name="fill_form",
        func=fill_form,
        description="Fill a form field on the currently open page.",
        parameters={
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "CSS selector or ID of the input field"},
                "value": {"type": "string", "description": "The value to fill"}
            },
            "required": ["selector", "value"]
        }
    )

    client.register_tool(
        name="web_search",
        func=web_search,
        description="Search the web for a query and return top results with titles and URLs.",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query"}
            },
            "required": ["query"]
        }
    )

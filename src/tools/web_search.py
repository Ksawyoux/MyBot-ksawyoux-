import asyncio
import logging
import time
from typing import List, Dict, Optional, Any
from duckduckgo_search import DDGS
import httpx

logger = logging.getLogger(__name__)

class WebSearchProxy:
    def __init__(self, region: str = "wt-wt", max_results: int = 5):
        self.region = region
        self.max_results = max_results
        self.timeout = 10
        self._last_search_time = 0
        self._search_interval = 2.0 # 2 seconds between searches to avoid 429

    async def _rate_limit(self):
        elapsed = time.time() - self._last_search_time
        if elapsed < self._search_interval:
            await asyncio.sleep(self._search_interval - elapsed)
        self._last_search_time = time.time()

    async def web_search(self, query: str, region: Optional[str] = None, max_results: Optional[int] = None) -> List[Dict[str, Any]]:
        """General web search."""
        if not query.strip():
            return []
            
        await self._rate_limit()
        region = region or self.region
        limit = max_results or self.max_results
        
        try:
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None, 
                lambda: list(DDGS().text(query, region=region, max_results=limit))
            )
            return results
        except Exception as e:
            logger.error(f"DDG General search error for query '{query}': {e}")
            return []

    async def news_search(self, query: str, region: Optional[str] = None, max_results: Optional[int] = None) -> List[Dict[str, Any]]:
        """Recent news articles."""
        region = region or self.region
        limit = max_results or self.max_results
        
        try:
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None, 
                lambda: list(DDGS().news(query, region=region, max_results=limit))
            )
            return results
        except Exception as e:
            logger.error(f"DDG News search error for query '{query}': {e}")
            return []

    async def instant_answer(self, query: str) -> Optional[Dict[str, Any]]:
        """Quick factual answers via DDG Chat."""
        try:
            loop = asyncio.get_event_loop()
            # DDGS().chat provides a direct response string
            response = await loop.run_in_executor(
                None, 
                lambda: DDGS().chat(query, model="gpt-4o-mini")
            )
            if response:
                return {"body": response, "href": "DuckDuckGo AI"}
            return None
        except Exception as e:
            logger.error(f"DDG Instant answer error for query '{query}': {e}")
            return None

def format_results_for_llm(results: List[Dict[str, Any]]) -> str:
    """Format search results for final display to the user."""
    if not results:
        return "No results found."
    
    formatted = []
    for i, res in enumerate(results, 1):
        title = res.get("title", "No Title")
        href = res.get("href", res.get("link", "#"))
        body = res.get("body", res.get("snippet", ""))
        formatted.append(f"{i}. {title}\n   URL: {href}\n   Snippet: {body}")
    
    return "\n\n".join(formatted)

def format_results_for_context(results: List[Dict[str, Any]]) -> str:
    """Compact results for injecting into LLM context."""
    if not results:
        return "Search returned no results."
    
    compact = []
    for res in results:
        title = res.get("title", "No Title")
        href = res.get("href", res.get("link", "#"))
        body = res.get("body", res.get("snippet", ""))
        # Limit body length for context
        compact.append(f"Title: {title} | URL: {href} | Content: {body[:300]}...")
    
    return "\n".join(compact)

# Singleton instance
search_tool = WebSearchProxy()

"""
src/mcp/servers/scraper_server.py — Web Scraper Tools (Read-only)
"""

import httpx
from bs4 import BeautifulSoup
from src.mcp.client import get_mcp_client
from src.utils.logging import get_logger

logger = get_logger(__name__)


async def fetch_page(url: str) -> dict:
    """Fetch and return cleaned text from a webpage."""
    logger.info("Fetching page: %s", url)
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, follow_redirects=True)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "html.parser")
            # Remove scripts and styles
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()

            text = soup.get_text(separator="\n")
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            cleaned_text = "\n".join(chunk for chunk in chunks if chunk)

            # Cap length to avoid massive token usage
            return {"content": cleaned_text[:15000]}
    except Exception as exc:
        return {"error": f"Failed to fetch {url}: {str(exc)}"}


async def search_web(query: str, num_results: int = 5) -> dict:
    """Lightweight DuckDuckGo HTML search."""
    logger.info("Searching web for: %s", query)
    try:
        url = "https://html.duckduckgo.com/html/"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        data = {"q": query}
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, headers=headers, data=data)
            resp.raise_for_status()
            
            soup = BeautifulSoup(resp.text, "html.parser")
            results = []
            
            for a in soup.find_all('a', class_='result__snippet')[:num_results]:
                href = a.get('href', '')
                if href.startswith('//duckduckgo.com/l/?uddg='):
                    import urllib.parse
                    href = urllib.parse.unquote(href.split('uddg=')[1].split('&')[0])
                
                results.append({
                    "snippet": a.text.strip(),
                    "link": href
                })
                
            return {"results": results}
    except Exception as exc:
        return {"error": f"Search failed: {str(exc)}"}


def register_scraper_tools() -> None:
    client = get_mcp_client()
    
    client.register_tool(
        name="fetch_page",
        func=fetch_page,
        description="Fetch readable text content from a URL.",
        parameters={
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"]
        }
    )
    
    client.register_tool(
        name="search_web",
        func=search_web,
        description="Search the web for recent information.",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "num_results": {"type": "integer", "description": "Max 10"}
            },
            "required": ["query"]
        }
    )

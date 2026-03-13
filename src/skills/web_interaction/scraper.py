"""
src/skills/web_interaction/scraper.py — Lightweight static content scraper.
"""

import httpx
from bs4 import BeautifulSoup
from typing import Optional, Dict, Any
from src.utils.logging import get_logger
from .safety import is_url_safe

logger = get_logger(__name__)

async def fetch_page(url: str, timeout: int = 30) -> Dict[str, Any]:
    """
    Fetches the static HTML content of a page using httpx.
    """
    safe, reason = is_url_safe(url)
    if not safe:
        return {"error": reason, "url": url}

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            
            return {
                "url": str(response.url),
                "status_code": response.status_code,
                "html": response.text,
                "content_type": response.headers.get("content-type", "")
            }
    except httpx.HTTPStatusError as e:
        logger.error("HTTP error fetching %s: %s", url, e)
        return {"error": f"HTTP {e.response.status_code}", "url": url}
    except Exception as e:
        logger.error("Error fetching %s: %s", url, e)
        return {"error": str(e), "url": url}

def parse_html(html: str) -> BeautifulSoup:
    """Parses HTML into a BeautifulSoup object."""
    return BeautifulSoup(html, "html.parser")

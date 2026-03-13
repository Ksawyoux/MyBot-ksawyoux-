import logging
import asyncio
from bs4 import BeautifulSoup
from typing import Dict, Any, Optional
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

async def fetch_url(url: str, max_chars: int = 15000, timeout: int = 30000) -> Dict[str, Any]:
    """
    Fetch URL using Playwright for full browser rendering.
    Handles JavaScript-heavy sites and extracts clean text.
    """
    # Safety checks
    if any(ext in url.lower() for ext in [".exe", ".zip", ".tar", ".gz", ".dmg", ".iso", ".bin", ".pdf"]):
        return {"status": "error", "reason": "Blocked: File download detected", "url": url}
    
    if any(p in url for p in ["localhost", "127.0.0.1", "192.168.", "10.0.", "172.16."]):
        return {"status": "error", "reason": "Blocked: Private IP address", "url": url}

    try:
        async with async_playwright() as p:
            # Launch browser (headless)
            browser = await p.chromium.launch(headless=True)
            
            # Create a context with a realistic user agent
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 800}
            )
            
            page = await context.new_page()
            
            # Navigate to URL
            logger.info(f"Navigating to {url} with Playwright...")
            response = await page.goto(url, wait_until="networkidle", timeout=timeout)
            
            if not response:
                await browser.close()
                return {"status": "error", "reason": "No response from page", "url": url}

            if response.status >= 400:
                status_code = response.status
                await browser.close()
                return {"status": "error", "reason": f"HTTP {status_code}", "url": url}

            # Get the rendered content and title
            content = await page.content()
            title = await page.title()
            
            await browser.close()

            # Use BeautifulSoup to clean HTML
            soup = BeautifulSoup(content, "lxml")
            
            # Remove noise
            noise_selectors = [
                 "script", "style", "nav", "footer", "header", "aside", "iframe",
                 "svg", "form", "button", "input", "textarea", "select",
                 "modal", ".modal", "#modal", "[role='dialog']", "noscript"
            ]
            for selector in noise_selectors:
                for tag in soup.select(selector) if selector.startswith((".", "#", "[")) else soup(selector):
                    tag.decompose()
            
            # Extract text with specific separator for better readability
            text = soup.get_text(separator="\n\n", strip=True)
            
            # Cleanup multiple newlines and extra spaces
            import re
            text = re.sub(r' +', ' ', text)
            text = re.sub(r'\n{3,}', '\n\n', text)
            
            # Truncate if necessary
            if len(text) > max_chars:
                text = text[:max_chars] + "... [truncated]"
            
            return {
                "status": "success",
                "url": url,
                "title": title or "No Title",
                "content": text
            }

    except asyncio.TimeoutError:
        logger.error(f"Timeout fetching {url}")
        return {"status": "error", "reason": "Timeout: Page took too long to load", "url": url}
    except Exception as e:
        logger.error(f"Error fetching {url} with Playwright: {e}")
        return {"status": "error", "reason": str(e), "url": url}

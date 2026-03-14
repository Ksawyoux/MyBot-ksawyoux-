"""
src/tools/web_interact.py — Playwright-based browser interaction with a pooled browser.

BrowserPool keeps a single Chromium instance alive for the process lifetime.
Each tool call gets a fresh page (cheap) instead of launching a new browser (expensive).
Call BrowserPool.close() on shutdown to release OS resources.
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_PRIVATE_PREFIXES = ("localhost", "127.0.0.1", "192.168.", "10.0.", "172.16.")
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


class BrowserPool:
    """Singleton that holds one persistent Chromium browser."""

    _playwright = None
    _browser = None
    _lock: asyncio.Lock | None = None

    @classmethod
    def _get_lock(cls) -> asyncio.Lock:
        if cls._lock is None:
            cls._lock = asyncio.Lock()
        return cls._lock

    @classmethod
    async def get_browser(cls):
        from playwright.async_api import async_playwright
        async with cls._get_lock():
            if cls._browser is None or not cls._browser.is_connected():
                if cls._playwright is None:
                    cls._playwright = await async_playwright().start()
                cls._browser = await cls._playwright.chromium.launch(headless=True)
                logger.info("Playwright: browser launched.")
        return cls._browser

    @classmethod
    async def new_page(cls):
        browser = await cls.get_browser()
        ctx = await browser.new_context(user_agent=_USER_AGENT)
        return await ctx.new_page()

    @classmethod
    async def close(cls):
        async with cls._get_lock():
            if cls._browser:
                await cls._browser.close()
                cls._browser = None
            if cls._playwright:
                await cls._playwright.stop()
                cls._playwright = None
            logger.info("Playwright: browser pool closed.")


def _is_private(url: str) -> bool:
    return any(p in url for p in _PRIVATE_PREFIXES)


def _extract_text(html: str, limit: int = 2000) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)
    return text[:limit] + "..." if len(text) > limit else text


async def get_interactive_elements(url: str, timeout: int = 30000) -> Dict[str, Any]:
    """Return clickable/typeable elements on a page."""
    if _is_private(url):
        return {"status": "error", "reason": "Blocked: Private IP address"}
    try:
        page = await BrowserPool.new_page()
        try:
            await page.goto(url, wait_until="networkidle", timeout=timeout)
            elements = await page.evaluate("""
                () => {
                    const items = [];
                    document.querySelectorAll('a, button, input, [role="button"], [onclick]').forEach((el, i) => {
                        if (el.offsetWidth > 0 && el.offsetHeight > 0) {
                            items.push({
                                index: i,
                                tag: el.tagName.toLowerCase(),
                                text: el.innerText?.trim() || el.value || el.placeholder || el.ariaLabel || "No text",
                                type: el.type || "N/A",
                                role: el.getAttribute('role') || "N/A",
                            });
                        }
                    });
                    return items.slice(0, 50);
                }
            """)
            title = await page.title()
        finally:
            await page.context.close()
        return {"status": "success", "url": url, "title": title, "elements": elements}
    except Exception as e:
        logger.error("Error listing elements for %s: %s", url, e)
        return {"status": "error", "reason": str(e)}


async def click_element(url: str, selector: str, wait_after: int = 2000) -> Dict[str, Any]:
    """Navigate to a URL and click a CSS selector."""
    try:
        page = await BrowserPool.new_page()
        try:
            await page.goto(url, wait_until="networkidle")
            await page.click(selector)
            await asyncio.sleep(wait_after / 1000)
            html = await page.content()
            new_url = page.url
            title = await page.title()
        finally:
            await page.context.close()
        return {
            "status": "success",
            "old_url": url,
            "new_url": new_url,
            "title": title,
            "content_preview": _extract_text(html),
        }
    except Exception as e:
        logger.error("Error clicking %s on %s: %s", selector, url, e)
        return {"status": "error", "reason": str(e)}


async def type_text(url: str, selector: str, text: str, press_enter: bool = True) -> Dict[str, Any]:
    """Fill an input and optionally press Enter."""
    try:
        page = await BrowserPool.new_page()
        try:
            await page.goto(url, wait_until="networkidle")
            await page.fill(selector, text)
            if press_enter:
                await page.press(selector, "Enter")
                await asyncio.sleep(3)
            html = await page.content()
            new_url = page.url
            title = await page.title()
        finally:
            await page.context.close()
        return {
            "status": "success",
            "url": new_url,
            "title": title,
            "content_preview": _extract_text(html),
        }
    except Exception as e:
        logger.error("Error typing into %s on %s: %s", selector, url, e)
        return {"status": "error", "reason": str(e)}

"""
src/skills/web_interaction/browser.py — Playwright-based dynamic browser engine.
"""

import asyncio
from typing import Optional, Dict, Any, List
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from src.utils.logging import get_logger
from .safety import is_url_safe, requires_approval
from .processor import get_page_state_representation

logger = get_logger(__name__)

class BrowserLifecycleManager:
    """
    Manages the lifecycle of the Playwright browser instance.
    Implements lazy start and inactivity timeout.
    """
    def __init__(self, inactivity_timeout: int = 60):
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._inactivity_timeout = inactivity_timeout
        self._last_activity = 0
        self._lock = asyncio.Lock()
        self._close_task: Optional[asyncio.Task] = None

    async def _start(self):
        async with self._lock:
            if not self._browser:
                logger.info("Starting Browser Engine (Playwright)...")
                self._playwright = await async_playwright().start()
                self._browser = await self._playwright.chromium.launch(headless=True)
                self._context = await self._browser.new_context(
                    viewport={"width": 1280, "height": 720},
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
                self._page = await self._context.new_page()
                self._schedule_close()

    def _schedule_close(self):
        if self._close_task:
            self._close_task.cancel()
        self._close_task = asyncio.create_task(self._close_after_timeout())

    async def _close_after_timeout(self):
        try:
            await asyncio.sleep(self._inactivity_timeout)
            await self.shutdown()
        except asyncio.CancelledError:
            pass

    async def shutdown(self):
        async with self._lock:
            if self._browser:
                logger.info("Shutting down Browser Engine due to inactivity.")
                await self._browser.close()
                await self._playwright.stop()
                self._browser = None
                self._playwright = None
                self._context = None
                self._page = None

    async def get_page(self) -> Page:
        if not self._browser:
            await self._start()
        self._last_activity = asyncio.get_event_loop().time()
        self._schedule_close()
        return self._page

# Global manager instance
browser_manager = BrowserLifecycleManager()

async def browse_url_dynamic(url: str) -> Dict[str, Any]:
    """
    Navigates to a URL using Playwright and returns the page state.
    """
    safe, reason = is_url_safe(url)
    if not safe:
        return {"error": reason, "url": url}

    try:
        page = await browser_manager.get_page()
        logger.info("Navigating to %s...", url)
        
        # Wait for network idle or timeout
        await page.goto(url, wait_until="networkidle", timeout=30000)
        
        # Simple scroll to trigger lazy loading
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(1) # Wait for potential lazy content
        
        html = await page.content()
        state = get_page_state_representation(html)
        
        return {
            "url": page.url,
            "title": await page.title(),
            "state": state
        }
    except Exception as e:
        logger.error("Browser error navigating to %s: %s", url, e)
        return {"error": str(e), "url": url}

async def perform_action(action_type: str, params: dict) -> Dict[str, Any]:
    """
    Performs an interaction on the currently open page.
    """
    page = await browser_manager.get_page()
    
    try:
        if action_type == "click":
            selector = params.get("selector")
            if not selector: return {"error": "No selector provided"}
            await page.click(selector, timeout=10000)
        elif action_type == "fill":
            selector = params.get("selector")
            value = params.get("value")
            if not selector or value is None: return {"error": "Missing selector or value"}
            await page.fill(selector, value, timeout=10000)
        elif action_type == "scroll":
            direction = params.get("direction", "down")
            if direction == "down":
                await page.evaluate("window.scrollBy(0, 500)")
            else:
                await page.evaluate("window.scrollBy(0, -500)")
        
        await asyncio.sleep(1) # Wait for page reaction
        html = await page.content()
        state = get_page_state_representation(html)
        
        return {
            "url": page.url,
            "state": state
        }
    except Exception as e:
        logger.error("Browser action error: %s", e)
        return {"error": str(e)}

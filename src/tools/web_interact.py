import logging
import asyncio
from typing import Dict, Any, List, Optional
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

async def get_interactive_elements(url: str, timeout: int = 30000) -> Dict[str, Any]:
    """
    Navigates to a URL and returns a list of interactive elements (buttons, links, inputs).
    This helps the agent decide what to interact with.
    """
    # Safety checks
    if any(p in url for p in ["localhost", "127.0.0.1", "192.168.", "10.0.", "172.16."]):
        return {"status": "error", "reason": "Blocked: Private IP address"}

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            
            await page.goto(url, wait_until="networkidle", timeout=timeout)
            
            # Extract interactive elements
            # We look for ahrefs, buttons, and inputs
            elements = await page.evaluate("""
                () => {
                    const interactives = [];
                    const sel = 'a, button, input, [role="button"], [onclick]';
                    document.querySelectorAll(sel).forEach((el, index) => {
                        // Only visible elements
                        if (el.offsetWidth > 0 && el.offsetHeight > 0) {
                            interactives.push({
                                index: index,
                                tag: el.tagName.toLowerCase(),
                                text: el.innerText.trim() || el.value || el.placeholder || el.ariaLabel || "No text",
                                type: el.type || "N/A",
                                role: el.getAttribute('role') || "N/A",
                                selector: `css=${el.tagName.toLowerCase()}:nth-of-type(${index + 1})` // Simple selector fallback
                            });
                        }
                    });
                    return interactives.slice(0, 50); // Limit to top 50
                }
            """)
            
            title = await page.title()
            await browser.close()
            
            return {
                "status": "success",
                "url": url,
                "title": title,
                "elements": elements
            }
    except Exception as e:
        logger.error(f"Error listing elements for {url}: {e}")
        return {"status": "error", "reason": str(e)}

async def click_element(url: str, selector: str, wait_after: int = 2000) -> Dict[str, Any]:
    """Navigates to a URL and clicks an element identified by a CSS selector."""
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, wait_until="networkidle")
            
            logger.info(f"Clicking element: {selector}")
            await page.click(selector)
            
            # Wait for any navigation or updates
            await asyncio.sleep(wait_after / 1000)
            
            # Capture the new state
            content = await page.content()
            new_url = page.url
            title = await page.title()
            
            await browser.close()
            
            # Extract text from the new state
            soup = BeautifulSoup(content, "lxml")
            for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
                tag.decompose()
            text = soup.get_text(separator="\n", strip=True)
            
            return {
                "status": "success",
                "old_url": url,
                "new_url": new_url,
                "title": title,
                "content_preview": text[:2000] + "..." if len(text) > 2000 else text
            }
    except Exception as e:
        logger.error(f"Error clicking {selector} on {url}: {e}")
        return {"status": "error", "reason": str(e)}

async def type_text(url: str, selector: str, text: str, press_enter: bool = True) -> Dict[str, Any]:
    """Fills an input field and optionally presses Enter."""
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, wait_until="networkidle")
            
            logger.info(f"Typing '{text}' into {selector}")
            await page.fill(selector, text)
            
            if press_enter:
                await page.press(selector, "Enter")
                await asyncio.sleep(3) # Wait for results
            
            content = await page.content()
            new_url = page.url
            title = await page.title()
            
            await browser.close()
            
            soup = BeautifulSoup(content, "lxml")
            for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
                tag.decompose()
            result_text = soup.get_text(separator="\n", strip=True)
            
            return {
                "status": "success",
                "url": new_url,
                "title": title,
                "content_preview": result_text[:2000] + "..." if len(result_text) > 2000 else result_text
            }
    except Exception as e:
        logger.error(f"Error typing into {selector} on {url}: {e}")
        return {"status": "error", "reason": str(e)}

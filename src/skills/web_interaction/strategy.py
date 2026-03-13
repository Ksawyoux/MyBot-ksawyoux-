"""
src/skills/web_interaction/strategy.py — Decision layer for choosing browsing method.
"""

import re
from typing import Tuple, List, Optional
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Heuristic: Domains that definitely need a browser
BROWSER_REQUIRED_DOMAINS = [
    r"linkedin\.com",
    r"twitter\.com",
    r"x\.com",
    r"facebook\.com",
    r"instagram\.com",
    r"github\.com", # For dynamic parts like code navigation
    r"app\.+",      # Many SaaS apps
    r"console\.+",  # Cloud consoles
]

def select_browsing_strategy(url: str) -> str:
    """
    Decides whether to use 'scraper' or 'browser' for a given URL.
    """
    for domain in BROWSER_REQUIRED_DOMAINS:
        if re.search(domain, url, re.IGNORECASE):
            logger.info("Strategy 'browser' selected for domain-specific rule: %s", url)
            return "browser"
    
    # Default to scraper for speed and efficiency
    logger.info("Strategy 'scraper' selected (default) for URL: %s", url)
    return "scraper"

def get_fallback_strategy(current_strategy: str) -> Optional[str]:
    """
    Returns the next strategy to try if the current one fails.
    """
    if current_strategy == "scraper":
        logger.info("Falling back from 'scraper' to 'browser'")
        return "browser"
    return None

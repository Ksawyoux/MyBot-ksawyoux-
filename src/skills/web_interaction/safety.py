"""
src/skills/web_interaction/safety.py — Guardrails for web browsing and interaction.
"""

import re
from typing import Optional, List, Tuple
from src.utils.logging import get_logger

logger = get_logger(__name__)

# List of domains that require human-in-the-loop (HITL) approval
SENSITIVE_DOMAINS = [
    r"github\.com",
    r"linkedin\.com",
    r"twitter\.com",
    r"x\.com",
    r"facebook\.com",
    r"amazon\.com",
    r"stripe\.com",
    r"paypal\.com",
    r"banking",
    r"login",
    r"auth",
]

# List of domains or URL patterns that are strictly blocked
BLOCKED_PATTERNS = [
    r"\.exe$",
    r"\.zip$",
    r"\.dmg$",
    r"\.iso$",
    r"malware",
    r"phishing",
    r"localhost",
    r"127\.0\.0\.1",
    r"169\.254\.169\.254",  # AWS Metadata service
]

def is_url_safe(url: str) -> Tuple[bool, str]:
    """
    Checks if a URL is safe to navigate to.
    Returns (is_safe, reason).
    """
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, url, re.IGNORECASE):
            logger.warning("URL blocked by pattern %s: %s", pattern, url)
            return False, f"URL blocked due to safety pattern: {pattern}"
    
    return True, "URL is safe"

def requires_approval(url: str, action: str = "navigate") -> bool:
    """
    Checks if an action on a specific URL requires HITL approval.
    """
    if action in ["fill_form", "click_button"]:
        # Form submission or button clicking is generally more sensitive
        return True

    for domain in SENSITIVE_DOMAINS:
        if re.search(domain, url, re.IGNORECASE):
            logger.info("URL %s requires approval due to sensitive domain match: %s", url, domain)
            return True
            
    return False

def sanitize_form_data(data: dict) -> dict:
    """
    Sanitizes sensitive data before it's sent to a website.
    In Phase 1, we just log and potentially mask common sensitive keys.
    """
    sensitive_keys = ["password", "token", "key", "secret", "cvv", "credit_card"]
    sanitized = data.copy()
    for key in sanitized:
        if any(sk in key.lower() for sk in sensitive_keys):
            logger.warning("Masking sensitive key in form data: %s", key)
            sanitized[key] = "********"
    return sanitized

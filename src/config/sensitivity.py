"""
src/config/sensitivity.py — Tool sensitivity for the approval gateway
"""

TOOL_SENSITIVITY: dict[str, bool] = {
    # Email
    "read_emails": False,
    "search_emails": False,
    "draft_email": False,
    "send_email": True,       # REQUIRES APPROVAL
    "delete_email": True,     # REQUIRES APPROVAL
    # Calendar
    "get_events": False,
    "check_availability": False,
    "create_event": True,     # REQUIRES APPROVAL
    "modify_event": True,     # REQUIRES APPROVAL
    "delete_event": True,     # REQUIRES APPROVAL
    # Scraper (all read-only)
    "fetch_page": False,
    "search_web": False,
    "extract_data": False,
    "screenshot_page": False,
}


def is_sensitive(tool_name: str) -> bool:
    return TOOL_SENSITIVITY.get(tool_name, False)

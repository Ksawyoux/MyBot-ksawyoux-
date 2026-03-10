"""
src/mcp/servers/calendar_server.py — Google Calendar tools
Stubbed implementation until OAuth/Service Account is fully configured.
"""

from typing import Optional
from src.config.settings import GOOGLE_CREDENTIALS_JSON
from src.mcp.client import get_mcp_client
from src.utils.logging import get_logger

logger = get_logger(__name__)


async def get_events(days: int = 7) -> dict:
    """Get upcoming events from the calendar."""
    if not GOOGLE_CREDENTIALS_JSON:
        # Stub response if not configured
        return {
            "events": [
                {"title": "Team Sync", "start": "2026-03-10T10:00:00Z", "duration_mins": 45},
                {"title": "Dentist", "start": "2026-03-12T14:30:00Z", "duration_mins": 60}
            ],
            "note": "Using stub data because GOOGLE_CREDENTIALS_JSON is not set."
        }
    return {"error": "Not implemented with real credentials yet."}


async def create_event(title: str, start_time: str, duration_mins: int) -> dict:
    """Create a new calendar event. (Requires Approval)"""
    logger.info("Creating event: %s at %s", title, start_time)
    if not GOOGLE_CREDENTIALS_JSON:
        return {"status": "success", "message": f"Stub: Created '{title}' at {start_time}"}
    return {"error": "Not implemented"}


def register_calendar_tools() -> None:
    client = get_mcp_client()
    
    client.register_tool(
        name="get_events",
        func=get_events,
        description="Get upcoming calendar events.",
        parameters={
            "type": "object",
            "properties": {"days": {"type": "integer", "default": 7}}
        }
    )
    
    client.register_tool(
        name="create_event",
        func=create_event,
        description="Create a new calendar event. Requires approval.",
        parameters={
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "start_time": {"type": "string", "description": "ISO 8601 datetime format"},
                "duration_mins": {"type": "integer", "default": 60}
            },
            "required": ["title", "start_time"]
        }
    )

"""
src/approval/gateway.py — Intercept sensitive actions
"""

from src.config.sensitivity import TOOL_SENSITIVITY
from src.approval.queue import create_approval_request
from src.utils.logging import get_logger

logger = get_logger(__name__)


async def wrap_tool_execution(tool_name: str, kwargs: dict, task_id: int) -> dict:
    """
    Check if a tool requires approval before executing.
    Returns the execution result OR a 'pending_approval' signal.
    """
    is_sensitive = TOOL_SENSITIVITY.get(tool_name, False)

    if not is_sensitive:
        logger.info("Tool '%s' is not sensitive, executing immediately.", tool_name)
        from src.mcp.client import get_mcp_client
        client = get_mcp_client()
        return await client.call_tool(tool_name, kwargs)

    # Prepare description based on the tool
    # TODO: Could format this better per-tool
    desc = f"Requesting permission to run '{tool_name}'"
    if tool_name == "send_email":
        desc = f"Send email to {kwargs.get('to_address')} regarding '{kwargs.get('subject')}'"
    elif tool_name == "create_event":
        desc = f"Create calendar event '{kwargs.get('title')}' at {kwargs.get('start_time')}"

    # Create the db record
    approval_id = create_approval_request(
        task_id=task_id,
        action_type=tool_name,
        description=desc,
        preview_data=kwargs
    )

    if approval_id == -1:
        logger.error("Failed to route '%s' to approval queue.", tool_name)
        return {"error": "Failed to create human approval request in DB"}

    logger.info("Tool '%s' intercepted. Created approval request #%d", tool_name, approval_id)
    return {
        "status": "pending_approval",
        "approval_id": approval_id,
        "description": desc,
        "details": "This action requires human approval. An interactive message will be sent."
    }

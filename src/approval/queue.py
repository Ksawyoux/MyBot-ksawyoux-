"""
src/approval/queue.py — Store and manage pending approvals
"""

import json
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import text
from src.config.settings import APPROVAL_TIMEOUT_HOURS
from src.db.connection import get_db
from src.utils.logging import get_logger

logger = get_logger(__name__)


def create_approval_request(
    task_id: int, action_type: str, description: str, preview_data: dict
) -> int:
    """Create a new pending approval row in the database."""
    expires = datetime.utcnow() + timedelta(hours=APPROVAL_TIMEOUT_HOURS)
    try:
        with get_db() as db:
            row = db.execute(
                text(
                    "INSERT INTO approvals (task_id, action_type, description, preview_data, expires_at) "
                    "VALUES (:tid, :act, :desc, :prev, :exp) RETURNING id"
                ),
                {
                    "tid": task_id,
                    "act": action_type,
                    "desc": description,
                    "prev": json.dumps(preview_data),
                    "exp": expires,
                },
            ).fetchone()
            return row[0] if row else -1
    except Exception as exc:
        logger.error("Failed to create approval request: %s", exc)
        return -1


def set_approval_message_id(approval_id: int, message_id: int) -> None:
    """Save the Telegram message ID so we can edit it later."""
    try:
        with get_db() as db:
            db.execute(
                text("UPDATE approvals SET telegram_msg_id = :msg_id WHERE id = :id"),
                {"msg_id": message_id, "id": approval_id},
            )
    except Exception as exc:
        logger.error("Failed to set approval msg ID: %s", exc)


def update_approval_status(approval_id: int, status: str) -> None:
    """Mark an approval as approved, rejected, or expired."""
    try:
        with get_db() as db:
            db.execute(
                text(
                    "UPDATE approvals SET status = :status, responded_at = NOW() "
                    "WHERE id = :id AND status = 'pending'"
                ),
                {"status": status, "id": approval_id},
            )
            logger.info("Approval %d marked as %s", approval_id, status)
    except Exception as exc:
        logger.error("Failed to update approval %d status: %s", approval_id, exc)


def get_pending_approvals() -> list[dict]:
    """Fetch all pending, non-expired approvals for the /pending command."""
    try:
        with get_db() as db:
            rows = db.execute(
                text(
                    "SELECT id, task_id, action_type, description, requested_at, expires_at "
                    "FROM approvals WHERE status = 'pending' AND expires_at > NOW() "
                    "ORDER BY requested_at ASC"
                )
            ).fetchall()
            return [
                {
                    "id": r[0],
                    "task_id": r[1],
                    "action_type": r[2],
                    "description": r[3],
                    "requested_at": str(r[4]),
                    "expires_at": str(r[5]),
                }
                for r in rows
            ]
    except Exception as exc:
        logger.error("Failed to fetch pending approvals: %s", exc)
        return []

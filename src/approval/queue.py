"""
src/approval/queue.py — Store and manage pending approvals
"""

import json
from datetime import datetime, timedelta
from typing import Optional

from src.config.settings import APPROVAL_TIMEOUT_HOURS
from src.db.connection import get_db
from src.db.models import Approval
from src.utils.logging import get_logger
from sqlalchemy import func

logger = get_logger(__name__)


def create_approval_request(
    task_id: int, action_type: str, description: str, preview_data: dict
) -> int:
    """Create a new pending approval row in the database."""
    expires = datetime.utcnow() + timedelta(hours=APPROVAL_TIMEOUT_HOURS)
    try:
        with get_db() as db:
            app = Approval(
                task_id=task_id,
                action_type=action_type,
                description=description,
                preview_data=preview_data,
                expires_at=expires
            )
            db.add(app)
            db.commit()
            db.refresh(app)
            return app.id
    except Exception as exc:
        logger.error("Failed to create approval request: %s", exc)
        return -1


def set_approval_message_id(approval_id: int, message_id: int) -> None:
    """Save the Telegram message ID so we can edit it later."""
    try:
        with get_db() as db:
            app = db.query(Approval).filter(Approval.id == approval_id).first()
            if app:
                app.telegram_msg_id = message_id
                db.commit()
    except Exception as exc:
        logger.error("Failed to set approval msg ID: %s", exc)


def update_approval_status(approval_id: int, status: str) -> None:
    """Mark an approval as approved, rejected, or expired."""
    try:
        with get_db() as db:
            app = db.query(Approval).filter(Approval.id == approval_id, Approval.status == 'pending').first()
            if app:
                app.status = status
                app.responded_at = func.now()
                db.commit()
                logger.info("Approval %d marked as %s", approval_id, status)
    except Exception as exc:
        logger.error("Failed to update approval %d status: %s", approval_id, exc)


def get_pending_approvals() -> list[dict]:
    """Fetch all pending, non-expired approvals for the /pending command."""
    try:
        with get_db() as db:
            now = datetime.utcnow()
            approvals = db.query(Approval).filter(
                Approval.status == 'pending',
                Approval.expires_at > now
            ).order_by(Approval.requested_at.asc()).all()
            
            return [
                {
                    "id": a.id,
                    "task_id": a.task_id,
                    "action_type": a.action_type,
                    "description": a.description,
                    "requested_at": str(a.requested_at),
                    "expires_at": str(a.expires_at),
                }
                for a in approvals
            ]
    except Exception as exc:
        logger.error("Failed to fetch pending approvals: %s", exc)
        return []

def get_approval(approval_id: int) -> Optional[dict]:
    """Fetch details of a specific approval."""
    try:
        with get_db() as db:
            app = db.query(Approval).filter(Approval.id == approval_id).first()
            if app:
                return {
                    "id": app.id,
                    "task_id": app.task_id,
                    "action_type": app.action_type,
                    "description": app.description,
                    "preview_data": app.preview_data or {},
                    "status": app.status
                }
    except Exception as exc:
        logger.error("Failed to fetch approval %d: %s", approval_id, exc)
    return None

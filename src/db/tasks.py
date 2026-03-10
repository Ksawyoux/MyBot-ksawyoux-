"""
src/db/tasks.py — Task tracking CRUD
"""

from typing import Optional
from src.db.connection import get_db
from src.db.models import TaskModel
from src.utils.logging import get_logger
from sqlalchemy import func
import json

logger = get_logger(__name__)


def create_task(
    task_type: str,
    input_data: Optional[dict] = None,
    priority: int = 2,
) -> int:
    """Create a task row in status 'pending'. Returns the new task id."""
    try:
        with get_db() as db:
            task = TaskModel(
                type=task_type,
                status='pending',
                priority=priority,
                input_data=input_data or {}
            )
            db.add(task)
            db.commit()
            db.refresh(task)
            return task.id
    except Exception as exc:
        logger.error("Failed to create task: %s", exc)
        return -1


def update_task(
    task_id: int,
    status: Optional[str] = None,
    model_used: Optional[str] = None,
    tokens_used: Optional[int] = None,
    output_data: Optional[dict] = None,
    error_message: Optional[str] = None,
) -> None:
    """Partial update on a task row."""
    try:
        with get_db() as db:
            task = db.query(TaskModel).filter(TaskModel.id == task_id).first()
            if not task:
                return

            if status:
                task.status = status
                if status == "in_progress":
                    task.started_at = func.now()
                elif status in ("completed", "failed", "cancelled"):
                    task.completed_at = func.now()
            if model_used:
                task.model_used = model_used
            if tokens_used is not None:
                task.tokens_used = tokens_used
            if output_data is not None:
                task.output_data = output_data
            if error_message:
                task.error_message = error_message

            db.commit()
    except Exception as exc:
        logger.error("Failed to update task %d: %s", task_id, exc)


def get_recent_tasks(limit: int = 10) -> list[dict]:
    """Return most recent tasks for /tasks command."""
    try:
        with get_db() as db:
            tasks = db.query(TaskModel).order_by(TaskModel.created_at.desc()).limit(limit).all()
            return [
                {
                    "id": t.id, "type": t.type, "status": t.status,
                    "model": t.model_used, "tokens": t.tokens_used, "created_at": str(t.created_at),
                }
                for t in tasks
            ]
    except Exception as exc:
        logger.error("Failed to get tasks: %s", exc)
        return []


def get_task_stats() -> dict:
    """Aggregate stats for /status command."""
    try:
        with get_db() as db:
            total = db.query(func.count(TaskModel.id)).scalar() or 0
            tokens_used = db.query(func.sum(TaskModel.tokens_used)).scalar() or 0
            completed = db.query(func.count(TaskModel.id)).filter(TaskModel.status == 'completed').scalar() or 0
            
            return {
                "total": total,
                "tokens_used": int(tokens_used),
                "completed": completed,
            }
    except Exception:
        return {}

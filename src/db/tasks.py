"""
src/db/tasks.py — Task tracking CRUD
"""

from typing import Optional
from sqlalchemy import text
from src.db.connection import get_db
from src.utils.logging import get_logger

logger = get_logger(__name__)


def create_task(
    task_type: str,
    input_data: Optional[dict] = None,
    priority: int = 2,
) -> int:
    """Create a task row in status 'pending'. Returns the new task id."""
    import json
    try:
        with get_db() as db:
            row = db.execute(
                text(
                    "INSERT INTO tasks (type, status, priority, input_data) "
                    "VALUES (:type, 'pending', :prio, :data) RETURNING id"
                ),
                {
                    "type": task_type,
                    "prio": priority,
                    "data": json.dumps(input_data or {}),
                },
            ).fetchone()
            return row[0] if row else -1
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
    import json
    fields = []
    params: dict = {"id": task_id}

    if status:
        fields.append("status = :status")
        params["status"] = status
        if status == "in_progress":
            fields.append("started_at = NOW()")
        elif status in ("completed", "failed", "cancelled"):
            fields.append("completed_at = NOW()")
    if model_used:
        fields.append("model_used = :model")
        params["model"] = model_used
    if tokens_used is not None:
        fields.append("tokens_used = :tokens")
        params["tokens"] = tokens_used
    if output_data is not None:
        fields.append("output_data = :out")
        params["out"] = json.dumps(output_data)
    if error_message:
        fields.append("error_message = :err")
        params["err"] = error_message

    if not fields:
        return
    sql = f"UPDATE tasks SET {', '.join(fields)} WHERE id = :id"
    try:
        with get_db() as db:
            db.execute(text(sql), params)
    except Exception as exc:
        logger.error("Failed to update task %d: %s", task_id, exc)


def get_recent_tasks(limit: int = 10) -> list[dict]:
    """Return most recent tasks for /tasks command."""
    try:
        with get_db() as db:
            rows = db.execute(
                text(
                    "SELECT id, type, status, model_used, tokens_used, created_at "
                    "FROM tasks ORDER BY created_at DESC LIMIT :lim"
                ),
                {"lim": limit},
            ).fetchall()
            return [
                {
                    "id": r[0], "type": r[1], "status": r[2],
                    "model": r[3], "tokens": r[4], "created_at": str(r[5]),
                }
                for r in rows
            ]
    except Exception as exc:
        logger.error("Failed to get tasks: %s", exc)
        return []


def get_task_stats() -> dict:
    """Aggregate stats for /status command."""
    try:
        with get_db() as db:
            row = db.execute(
                text(
                    "SELECT COUNT(*), "
                    "COALESCE(SUM(tokens_used), 0), "
                    "COUNT(*) FILTER (WHERE status='completed') "
                    "FROM tasks"
                )
            ).fetchone()
            return {
                "total": row[0] or 0,
                "tokens_used": row[1] or 0,
                "completed": row[2] or 0,
            }
    except Exception:
        return {}

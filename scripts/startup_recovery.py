"""
scripts/startup_recovery.py — Recover suspended tasks on boot
"""

from sqlalchemy import text
from src.db.connection import get_db
from src.utils.logging import get_logger

logger = get_logger(__name__)


def recover_stuck_tasks() -> None:
    """
    Find tasks that were 'in_progress' when the application crashed/restarted
    and mark them as 'failed' so they don't block queues indefinitely.
    """
    logger.info("Running startup recovery loop...")
    try:
        with get_db() as db:
            result = db.execute(
                text(
                    "UPDATE tasks SET status = 'failed', "
                    "error_message = 'Task interrupted by system restart' "
                    "WHERE status = 'in_progress'"
                )
            )
            count = result.rowcount
            if count > 0:
                logger.warning("Recovered %d stuck tasks.", count)
            else:
                logger.info("No stuck tasks found.")
                
            # Clean up expired approvals
            result = db.execute(
                text(
                    "UPDATE approvals SET status = 'expired' "
                    "WHERE status = 'pending' AND expires_at < NOW()"
                )
            )
            acount = result.rowcount
            if acount > 0:
                logger.info("Expired %d old approval requests.", acount)
                
    except Exception as exc:
        logger.error("Startup recovery failed: %s", exc)

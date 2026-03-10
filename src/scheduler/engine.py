"""
src/scheduler/engine.py — Background task scheduler using APScheduler
"""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED

from src.config.settings import SUPABASE_DB_URL
from src.utils.logging import get_logger
import warnings

logger = get_logger(__name__)

# Ignore SQLAlchemy pool warnings from APScheduler
warnings.filterwarnings("ignore", category=UserWarning, module="apscheduler")

_scheduler = None


def init_scheduler() -> BackgroundScheduler:
    """Initialize APScheduler with Supabase storage."""
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    logger.info("Initializing background scheduler...")

    # We use SQLAlchemyJobStore to persist jobs across restarts.
    # Note: Using the direct SUPABASE_DB_URL. NullPool is preferable but APScheduler handles it okay.
    jobstores = {
        # Using a specific table name so it doesn't conflict with our manual schemas
        "default": SQLAlchemyJobStore(url=SUPABASE_DB_URL, tablename="apscheduler_jobs")
    }
    
    _scheduler = BackgroundScheduler(jobstores=jobstores)

    # Add basic event listeners for logging
    def job_listener(event):
        if event.exception:
            logger.error("Job %s crashed: %s", event.job_id, event.exception)
        else:
            logger.info("Job %s executed successfully.", event.job_id)

    _scheduler.add_listener(job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)
    _scheduler.start()
    
    logger.info("Scheduler started successfully.")
    return _scheduler


def get_scheduler() -> BackgroundScheduler:
    """Return the running scheduler instance."""
    global _scheduler
    if _scheduler is None:
        return init_scheduler()
    return _scheduler

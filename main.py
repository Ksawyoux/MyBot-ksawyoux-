"""
src/main.py — Application entry point
Starts the Telegram bot and the Flask health server in parallel threads.
"""

import threading
import asyncio
import sys
import signal
from typing import Any

from src.utils.logging import get_logger
from src.config.settings import HEALTH_PORT
from src.db.connection import test_connection
from src.bot.telegram_bot import build_application
from scripts.health_ping import run_health_server
from src.scheduler.engine import get_scheduler
from scripts.startup_recovery import recover_stuck_tasks
from src.mcp.tools_registry import init_tools

logger = get_logger(__name__)


def run_bot() -> None:
    """Run the Telegram bot in polling mode (blocking)."""
    app = build_application()
    logger.info("Starting Telegram bot (polling)...")
    app.run_polling(drop_pending_updates=True)


def shutdown_handler(signum, frame):
    """Handle graceful shutdown signals."""
    logger.info("Received signal %d. Shutting down gracefully...", signum)
    
    # 1. Stop APScheduler
    try:
        scheduler = get_scheduler()
        if scheduler.running:
            scheduler.shutdown(wait=False)
            logger.info("Scheduler shutdown complete.")
    except Exception as e:
        logger.error("Error shutting down scheduler: %s", e)

    # 2. Stop LLM Queue (if applicable)
    try:
        from src.llm.request_queue import get_request_queue
        get_request_queue().stop()
        logger.info("LLM Request Queue shutdown complete.")
    except Exception as e:
        logger.error("Error shutting down LLM Queue: %s", e)

    # 3. Close Playwright browser pool
    try:
        import asyncio
        from src.tools.web_interact import BrowserPool
        asyncio.get_event_loop().run_until_complete(BrowserPool.close())
    except Exception as e:
        logger.error("Error closing browser pool: %s", e)

    logger.info("Exiting.")
    sys.exit(0)


def main() -> None:
    logger.info("=" * 50)
    logger.info("AI Agent System — Starting up")
    logger.info("=" * 50)

    # Register signal handlers
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    try:
        # Verify DB is reachable before starting
        if not test_connection():
            logger.critical("Database not reachable. Aborting startup.")
            sys.exit(1)

        # Run recovery cleanups
        recover_stuck_tasks()

        # Initialize MCP Tools
        init_tools()

        # Pre-warm skill prompt cache so first intent parse doesn't hit disk
        from src.router.intent_parser import refresh_skill_cache
        refresh_skill_cache()

        # Health server runs in a daemon thread
        health_thread = threading.Thread(
            target=run_health_server,
            args=(HEALTH_PORT,),
            daemon=True,
            name="health-server",
        )
        health_thread.start()
        logger.info("Health server thread started on port %d", HEALTH_PORT)


        # Start the APScheduler engine
        scheduler = get_scheduler()

        # Phase 09 - Register the daily 08:00 Morning Briefing
        from apscheduler.triggers.cron import CronTrigger
        from src.scheduler.jobs import run_morning_briefing
        from src.config.settings import TELEGRAM_ADMIN_USER_ID
        
        # We use the admin's Telegram ID as the primary session ID for system jobs
        job_id = "daily_morning_briefing"
        if not scheduler.get_job(job_id):
            scheduler.add_job(
                run_morning_briefing,
                trigger=CronTrigger(hour=8, minute=0),
                args=[str(TELEGRAM_ADMIN_USER_ID)],
                id=job_id,
                name="Daily Morning Briefing",
                replace_existing=True
            )
            logger.info("Registered daily morning briefing job for 08:00.")

        # Hourly cleanup of expired approvals
        from src.approval.queue import expire_stale_approvals
        if not scheduler.get_job("expire_approvals"):
            scheduler.add_job(
                expire_stale_approvals,
                trigger="interval",
                hours=1,
                id="expire_approvals",
                name="Expire Stale Approvals",
                replace_existing=True,
            )
            logger.info("Registered hourly approval expiry job.")

        # Telegram bot runs on the main thread
        run_bot()

    except Exception as exc:
        logger.critical("Fatal error during startup: %s", exc, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

"""
scripts/health_ping.py — Flask health endpoint
Pings the database to prevent Supabase 7-day inactivity pause.
Responds to external keep-alive cron (prevents Render sleep).
"""

from flask import Flask, jsonify
from datetime import datetime

from src.db.connection import engine
from src.utils.logging import get_logger
from sqlalchemy import text

logger = get_logger(__name__)
app = Flask(__name__)


@app.route("/health")
def health():
    """
    Health check endpoint:
    - Returns 200 with status JSON
    - Pings DB to prevent Supabase sleep
    """
    db_status = "unknown"
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as exc:
        db_status = f"error: {str(exc)}"
        logger.error("Health check DB ping failed: %s", exc)

    return jsonify(
        {
            "status": "ok",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "database": db_status,
        }
    ), 200


def run_health_server(port: int = 8000) -> None:
    logger.info("Starting health server on port %d", port)
    app.run(host="0.0.0.0", port=port, use_reloader=False)


if __name__ == "__main__":
    import os
    run_health_server(int(os.getenv("HEALTH_PORT", "8000")))

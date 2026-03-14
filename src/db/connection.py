"""
src/db/connection.py — SQLAlchemy connection to Supabase via NullPool

Connection strategy:
  Supabase uses Supavisor (an external PgBouncer-compatible pooler) on port 6543.
  Using SQLAlchemy's NullPool means every get_db() gets a fresh connection from
  Supavisor rather than a second application-level pool — avoids double-pooling.
  keepalives_* settings prevent Supavisor from closing idle connections mid-request.
"""

from sqlalchemy import create_engine, event, text
from sqlalchemy.pool import NullPool
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
from typing import Generator

from src.config.settings import SUPABASE_DB_URL
from src.utils.logging import get_logger

logger = get_logger(__name__)

engine = create_engine(
    SUPABASE_DB_URL,
    poolclass=NullPool,
    echo=False,
    connect_args={
        "connect_timeout": 10,
        "options": "-c timezone=utc",
        # Keep TCP connections alive so Supavisor doesn't kill idle ones
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 5,
    },
)

# Verify each new connection is alive before handing it to the application.
# With NullPool this runs once per get_db() call — negligible overhead.
@event.listens_for(engine, "connect")
def _on_connect(dbapi_conn, _record):
    try:
        dbapi_conn.cursor().execute("SELECT 1")
    except Exception:
        raise

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """Context manager yielding a DB session; commits on success, rolls back on error."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def test_connection() -> bool:
    """Verify database reachability."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Database connection: OK")
        return True
    except Exception as exc:
        logger.error("Database connection failed: %s", exc)
        return False

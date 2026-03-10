"""
src/db/connection.py — SQLAlchemy connection to Supabase via NullPool
"""

from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
from typing import Generator

from src.config.settings import SUPABASE_DB_URL
from src.utils.logging import get_logger

logger = get_logger(__name__)

# NullPool — Supabase uses Supavisor; avoid double-pooling
engine = create_engine(
    SUPABASE_DB_URL,
    poolclass=NullPool,
    echo=False,
    connect_args={
        "connect_timeout": 10,
        "options": "-c timezone=utc",
    },
)

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

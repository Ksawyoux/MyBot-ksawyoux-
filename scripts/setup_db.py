"""
scripts/setup_db.py — Bootstrap Supabase schema
Run once to create all tables and enable pgvector.
"""

import sys
import os

# Allow running as a standalone script
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.connection import engine, test_connection
from src.utils.logging import get_logger
from sqlalchemy import text

logger = get_logger(__name__)

SCHEMA_SQL = """
-- pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Conversations
CREATE TABLE IF NOT EXISTS conversations (
    id SERIAL PRIMARY KEY,
    session_id TEXT NOT NULL,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    tokens INTEGER,
    summarized BOOLEAN DEFAULT FALSE,
    summary_id INTEGER
);
CREATE INDEX IF NOT EXISTS idx_conversations_session ON conversations(session_id);
CREATE INDEX IF NOT EXISTS idx_conversations_timestamp ON conversations(timestamp);

-- Summaries
CREATE TABLE IF NOT EXISTS summaries (
    id SERIAL PRIMARY KEY,
    session_id TEXT NOT NULL,
    content TEXT NOT NULL,
    tokens INTEGER,
    messages_start INTEGER,
    messages_end INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_summaries_session ON summaries(session_id);

-- Facts (long-term memory)
CREATE TABLE IF NOT EXISTS facts (
    id SERIAL PRIMARY KEY,
    category TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    context TEXT,
    confidence REAL DEFAULT 1.0,
    source_session TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    access_count INTEGER DEFAULT 0,
    superseded_by INTEGER REFERENCES facts(id)
);
CREATE INDEX IF NOT EXISTS idx_facts_category ON facts(category);
CREATE INDEX IF NOT EXISTS idx_facts_key ON facts(key);

-- Memory embeddings (pgvector)
CREATE TABLE IF NOT EXISTS memory_embeddings (
    id SERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    embedding VECTOR(384),
    metadata JSONB,
    type TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_memory_type ON memory_embeddings(type);

-- Tasks
CREATE TABLE IF NOT EXISTS tasks (
    id SERIAL PRIMARY KEY,
    type TEXT NOT NULL,
    status TEXT NOT NULL,
    priority INTEGER DEFAULT 2,
    input_data JSONB,
    output_data JSONB,
    output_text TEXT,
    output_media JSONB,
    agent_used TEXT,
    model_used TEXT,
    llm_calls INTEGER DEFAULT 0,
    tokens_used INTEGER DEFAULT 0,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    checkpoint JSONB
);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_created ON tasks(created_at);

-- Approvals
CREATE TABLE IF NOT EXISTS approvals (
    id SERIAL PRIMARY KEY,
    task_id INTEGER REFERENCES tasks(id),
    action_type TEXT NOT NULL,
    description TEXT,
    preview_data JSONB,
    status TEXT DEFAULT 'pending',
    telegram_msg_id BIGINT,
    requested_at TIMESTAMPTZ DEFAULT NOW(),
    responded_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_approvals_status ON approvals(status);
CREATE INDEX IF NOT EXISTS idx_approvals_task ON approvals(task_id);

-- Scheduled jobs
CREATE TABLE IF NOT EXISTS scheduled_jobs (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    schedule_type TEXT NOT NULL,
    schedule_value TEXT NOT NULL,
    task_template JSONB NOT NULL,
    approval_mode TEXT DEFAULT 'each_time',
    enabled BOOLEAN DEFAULT TRUE,
    last_run TIMESTAMPTZ,
    next_run TIMESTAMPTZ,
    run_count INTEGER DEFAULT 0,
    fail_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_scheduled_jobs_enabled ON scheduled_jobs(enabled);
CREATE INDEX IF NOT EXISTS idx_scheduled_jobs_next_run ON scheduled_jobs(next_run);

-- Response cache
CREATE TABLE IF NOT EXISTS cache (
    id SERIAL PRIMARY KEY,
    prompt_hash TEXT UNIQUE NOT NULL,
    prompt_preview TEXT,
    response TEXT NOT NULL,
    model_used TEXT,
    tokens_saved INTEGER,
    hit_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    last_hit TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_cache_hash ON cache(prompt_hash);
CREATE INDEX IF NOT EXISTS idx_cache_expires ON cache(expires_at);

-- System state
CREATE TABLE IF NOT EXISTS system_state (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Output History
CREATE TABLE IF NOT EXISTS output_history (
    id SERIAL PRIMARY KEY,
    task_id INTEGER REFERENCES tasks(id),
    sequence_number INTEGER DEFAULT 1,
    output_envelope JSONB,
    rendered_for TEXT,
    telegram_msg_id BIGINT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_output_history_task ON output_history(task_id);

-- Output Files
CREATE TABLE IF NOT EXISTS output_files (
    id SERIAL PRIMARY KEY,
    task_id INTEGER REFERENCES tasks(id),
    file_type TEXT,
    storage_path TEXT,
    file_size BIGINT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_output_files_task ON output_files(task_id);

-- Safe migrations for SQLite/Postgres to add columns if they don't exist
DO $$
BEGIN
    BEGIN
        ALTER TABLE tasks ADD COLUMN output_text TEXT;
    EXCEPTION
        WHEN duplicate_column THEN NULL;
    END;
    BEGIN
        ALTER TABLE tasks ADD COLUMN output_media JSONB;
    EXCEPTION
        WHEN duplicate_column THEN NULL;
    END;
END $$;
"""


def setup_database() -> None:
    logger.info("Testing database connection...")
    if not test_connection():
        logger.error("Cannot reach database. Check SUPABASE_DB_URL.")
        sys.exit(1)

    logger.info("Running schema bootstrap...")
    with engine.connect() as conn:
        # Split on semicolons and execute each statement
        for statement in SCHEMA_SQL.split(";"):
            stmt = statement.strip()
            if stmt:
                conn.execute(text(stmt))
        conn.commit()

    logger.info("✅ Schema bootstrapped successfully.")


if __name__ == "__main__":
    setup_database()

# ARCHITECTURE.md — AI Agent System Design

> This is the full system design document. For a quick reference, see [CLAUDE.md](./CLAUDE.md).

## Architecture Summary

```
User (Telegram) → Bot Layer → Request Router → Task Classifier
                                                      │
                         ┌────────────────────────────┼────────────────────────────┐
                         │                            │                            │
                         ▼                            ▼                            ▼
                   Simple Tasks              Complex Tasks               Scheduled Tasks
                   (Direct LLM)              (CrewAI Agents)              (Job Scheduler)
                         │                            │                            │
                         └────────────────────────────┼────────────────────────────┘
                                                      │
                                                      ▼
                                              Approval Gateway
                                          (sensitive tasks wait)
                                                      │
                                                      ▼
                                               MCP Client
                                                      │
                                   ┌──────────────────┼──────────────────┐
                                   │                  │                  │
                                   ▼                  ▼                  ▼
                            Email Server      Calendar Server     Scraper Server
                                   │                  │                  │
                                   ▼                  ▼                  ▼
                              Gmail/IMAP        Google Calendar      Web/APIs
```

## Model Configuration

```python
# src/config/models.py

MODEL_TIERS = {
    "lightweight": {
        "primary": "mistralai/mistral-7b-instruct",
        "fallback": "google/gemma-7b-it",
        "tasks": ["classification", "simple_qa", "formatting", "intent_parsing"]
    },
    "balanced": {
        "primary": "meta-llama/llama-3-8b-instruct",
        "fallback": "mistralai/mixtral-8x7b-instruct",
        "tasks": ["email_drafting", "summarization", "data_extraction", "calendar_parsing"]
    },
    "capable": {
        "primary": "meta-llama/llama-3-70b-instruct",
        "fallback": "mistralai/mixtral-8x7b-instruct",
        "tasks": ["research", "complex_reasoning", "planning", "creative_writing"]
    },
    "system": {
        "primary": "mistralai/mistral-7b-instruct",
        "tasks": ["fact_extraction", "summarization_internal"]
    }
}

RATE_LIMITS = {
    "requests_per_minute": 10,
    "requests_per_hour": 100,
    "max_concurrent": 2,
    "cooldown_on_429": 60  # seconds
}
```

## Tool Sensitivity Configuration

```python
# src/config/sensitivity.py

TOOL_SENSITIVITY = {
    # Email tools
    "read_emails": False,
    "search_emails": False,
    "draft_email": False,
    "send_email": True,      # REQUIRES APPROVAL
    "delete_email": True,    # REQUIRES APPROVAL
    
    # Calendar tools
    "get_events": False,
    "check_availability": False,
    "create_event": True,    # REQUIRES APPROVAL
    "modify_event": True,    # REQUIRES APPROVAL
    "delete_event": True,    # REQUIRES APPROVAL
    
    # Scraper tools (all read-only)
    "fetch_page": False,
    "search_web": False,
    "extract_data": False,
    "screenshot_page": False,
}
```

## Database Schema

### PostgreSQL Tables (Supabase)

```sql
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Conversations
CREATE TABLE conversations (
    id SERIAL PRIMARY KEY,
    session_id TEXT NOT NULL,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    role TEXT NOT NULL,  -- user/assistant/system
    content TEXT NOT NULL,
    tokens INTEGER,
    summarized BOOLEAN DEFAULT FALSE,
    summary_id INTEGER REFERENCES summaries(id)
);

CREATE INDEX idx_conversations_session ON conversations(session_id);
CREATE INDEX idx_conversations_timestamp ON conversations(timestamp);

-- Summaries
CREATE TABLE summaries (
    id SERIAL PRIMARY KEY,
    session_id TEXT NOT NULL,
    content TEXT NOT NULL,
    tokens INTEGER,
    messages_start INTEGER,
    messages_end INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_summaries_session ON summaries(session_id);

-- Facts (long-term knowledge)
CREATE TABLE facts (
    id SERIAL PRIMARY KEY,
    category TEXT NOT NULL,  -- preference/knowledge/pattern/entity
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    context TEXT,  -- optional: work/personal
    confidence REAL DEFAULT 1.0,
    source_session TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    access_count INTEGER DEFAULT 0,
    superseded_by INTEGER REFERENCES facts(id)
);

CREATE INDEX idx_facts_category ON facts(category);
CREATE INDEX idx_facts_key ON facts(key);

-- Memory embeddings (pgvector)
CREATE TABLE memory_embeddings (
    id SERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    embedding VECTOR(384),  -- all-MiniLM-L6-v2 dimensions
    metadata JSONB,
    type TEXT NOT NULL,  -- fact/summary/preference
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create index for similarity search
CREATE INDEX ON memory_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

CREATE INDEX idx_memory_type ON memory_embeddings(type);

-- Tasks
CREATE TABLE tasks (
    id SERIAL PRIMARY KEY,
    type TEXT NOT NULL,  -- simple/complex/scheduled
    status TEXT NOT NULL,  -- pending/in_progress/awaiting_approval/approved/completed/failed/cancelled
    priority INTEGER DEFAULT 2,  -- 0=highest, 3=lowest
    input_data JSONB,
    output_data JSONB,
    agent_used TEXT,
    model_used TEXT,
    llm_calls INTEGER DEFAULT 0,
    tokens_used INTEGER DEFAULT 0,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    checkpoint JSONB  -- for recovery
);

CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_created ON tasks(created_at);

-- Approvals
CREATE TABLE approvals (
    id SERIAL PRIMARY KEY,
    task_id INTEGER REFERENCES tasks(id),
    action_type TEXT NOT NULL,
    description TEXT,
    preview_data JSONB,
    status TEXT DEFAULT 'pending',  -- pending/approved/rejected/expired
    telegram_msg_id BIGINT,
    requested_at TIMESTAMPTZ DEFAULT NOW(),
    responded_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ
);

CREATE INDEX idx_approvals_status ON approvals(status);
CREATE INDEX idx_approvals_task ON approvals(task_id);

-- Scheduled jobs
CREATE TABLE scheduled_jobs (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    schedule_type TEXT NOT NULL,  -- once/cron/interval
    schedule_value TEXT NOT NULL,
    task_template JSONB NOT NULL,
    approval_mode TEXT DEFAULT 'each_time',  -- pre_approved/each_time/review_window
    enabled BOOLEAN DEFAULT TRUE,
    last_run TIMESTAMPTZ,
    next_run TIMESTAMPTZ,
    run_count INTEGER DEFAULT 0,
    fail_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_scheduled_jobs_enabled ON scheduled_jobs(enabled);
CREATE INDEX idx_scheduled_jobs_next_run ON scheduled_jobs(next_run);

-- Response cache
CREATE TABLE cache (
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

CREATE INDEX idx_cache_hash ON cache(prompt_hash);
CREATE INDEX idx_cache_expires ON cache(expires_at);

-- System state
CREATE TABLE system_state (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

## Database Connection

### Supabase Connection Setup

```python
# src/db/connection.py

import os
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool
from sqlalchemy.orm import sessionmaker

# Use Supabase pooled connection string
DATABASE_URL = os.getenv("SUPABASE_DB_URL")

# Supabase handles connection pooling via Supavisor
# Use NullPool to avoid double-pooling
engine = create_engine(
    DATABASE_URL,
    poolclass=NullPool,
    echo=False,
    connect_args={
        "connect_timeout": 10,
        "options": "-c timezone=utc"
    }
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """Database session dependency"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def test_connection():
    """Test database connectivity"""
    try:
        with engine.connect() as conn:
            result = conn.execute("SELECT 1")
            return True
    except Exception as e:
        print(f"Database connection failed: {e}")
        return False
```

### Health Check (DB Ping to Prevent Pause)

```python
# scripts/health_ping.py

from flask import Flask, jsonify
from datetime import datetime
from src.db.connection import engine

app = Flask(__name__)

@app.route('/health')
def health():
    """
    Health check endpoint
    - Responds to external ping services (prevents Render sleep)
    - Pings Supabase database (prevents 7-day inactivity pause)
    """
    try:
        # Ping database
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    return jsonify({
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "database": db_status
    }), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
```

## Key Component Flows

### LLM Gateway Flow

```
Request → Cache Check → Rate Limiter → Priority Queue → Model Router → Fallback Chain → OpenRouter
              │                                                                              │
              │ (cache hit)                                                                  │
              └──────────────────────────────► Response ◄────────────────────────────────────┘
```

**Priority Levels:**
- P0: Interactive (user waiting)
- P1: Approval responses
- P2: Background tasks
- P3: Scheduled/low priority

### Memory Flow

```
User Message
     │
     ▼
┌─────────────────┐
│ Load Context    │
│                 │
│ • Working mem   │
│ • Short-term    │
│ • Relevant long │
│   term (search) │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Token Count     │
│ > Threshold?    │
└────────┬────────┘
         │
    YES  │
         ▼
┌─────────────────┐
│ Summarize old   │
│ Extract facts   │
│ Store in LTM    │
└────────┬────────┘
         │
         ▼
   Send to LLM
```

### Memory Conflict Resolution

When conflicting facts detected:
1. Notify user via Telegram
2. Present both facts with timestamps
3. Offer options: [Use NEW] [Keep OLD] [Context-dependent]
4. Store resolution

### Approval Flow

```
Sensitive Tool Called
         │
         ▼
┌─────────────────────────────────┐
│  Create Approval Request        │
│                                 │
│  • Store in approvals table     │
│  • Send Telegram message with:  │
│    - Action description         │
│    - Preview of what will happen│
│    - [✅ Approve] [❌ Reject]   │
│      [✏️ Edit] buttons          │
└────────────────┬────────────────┘
                 │
                 ▼
         Wait for callback
                 │
    ┌────────────┼────────────┐
    │            │            │
    ▼            ▼            ▼
 Approved     Rejected      Timeout
    │            │            │
    ▼            │            │
 Execute         └──── Mark failed, notify
```

### Startup Recovery

```
System Start
     │
     ├── 1. Health check (DB, APIs)
     │
     ├── 2. Load persistent state
     │
     ├── 3. Query pending tasks
     │       └── Resume non-destructive
     │       └── Ask user for destructive
     │
     ├── 4. Query pending approvals
     │       └── Re-notify if still valid
     │
     ├── 5. Reload scheduled jobs
     │       └── Recalculate next_run
     │       └── Handle missed (<15min: run, >1hr: skip)
     │
     ├── 6. Notify user of status
     │
     └── 7. Start all services
```

## MCP Servers

### Email MCP Server

```python
# Tools exposed:
# - read_emails(folder, count, filter) → List[Email]
# - search_emails(query, date_range) → List[Email]
# - draft_email(to, subject, body) → DraftID
# - send_email(draft_id) → Success [APPROVAL REQUIRED]
# - delete_email(email_id) → Success [APPROVAL REQUIRED]
```

### Calendar MCP Server

```python
# Tools exposed:
# - get_events(date_range) → List[Event]
# - check_availability(date_range) → List[FreeSlot]
# - create_event(title, time, duration, attendees) → EventID [APPROVAL REQUIRED]
# - modify_event(event_id, changes) → Success [APPROVAL REQUIRED]
# - delete_event(event_id) → Success [APPROVAL REQUIRED]
```

### Scraper MCP Server

```python
# Tools exposed:
# - fetch_page(url) → CleanedText
# - search_web(query, num_results) → List[SearchResult]
# - extract_data(url, schema) → StructuredJSON
# - screenshot_page(url) → ImageBytes
```

### Querying Memory Embeddings (Semantic Search)

```python
# src/memory/long_term.py

from pgvector.sqlalchemy import Vector
from sqlalchemy import select, func

def search_memory(query_text: str, limit: int = 5):
    """Search long-term memory using semantic similarity"""
    
    # Generate embedding for query
    query_embedding = generate_embedding(query_text)
    
    # Cosine similarity search
    stmt = select(
        memory_embeddings.c.content,
        memory_embeddings.c.metadata,
        memory_embeddings.c.embedding.cosine_distance(query_embedding).label('distance')
    ).order_by('distance').limit(limit)
    
    results = db.execute(stmt).fetchall()
    return results
```

## Deployment

### Supabase Setup

#### 1. Create Project

```bash
1. Go to supabase.com
2. Create new project
3. Choose region (US West recommended for Render Oregon)
4. Set strong database password (save it!)
5. Wait ~2 minutes for provisioning
```

#### 2. Enable pgvector

```sql
-- In Supabase SQL Editor
CREATE EXTENSION IF NOT EXISTS vector;
```

#### 3. Run Schema

```sql
-- Copy entire schema from above
-- Paste in Supabase SQL Editor
-- Execute
```

#### 4. Get Connection String

```
Supabase Dashboard → Settings → Database

Connection string (pooled):
postgresql://postgres:[PASSWORD]@aws-0-[region].pooler.supabase.com:6543/postgres

Use this in SUPABASE_DB_URL
```

#### 5. Configure Project Settings

```
Supabase Dashboard → Settings → API

Copy:
- Project URL → SUPABASE_URL
- anon/public key → SUPABASE_ANON_KEY
- service_role key → SUPABASE_SERVICE_KEY
```

### Render Setup

#### render.yaml

```yaml
services:
  - type: web
    name: ai-agent
    env: python
    plan: free
    buildCommand: pip install -r requirements.txt
    startCommand: python src/main.py
    healthCheckPath: /health
    envVars:
      - key: TELEGRAM_BOT_TOKEN
        sync: false
      - key: OPENROUTER_API_KEY
        sync: false
      - key: SUPABASE_URL
        sync: false
      - key: SUPABASE_DB_URL
        sync: false
      - key: SUPABASE_ANON_KEY
        sync: false
      - key: SUPABASE_SERVICE_KEY
        sync: false
      - key: EMAIL_ADDRESS
        sync: false
      - key: EMAIL_PASSWORD
        sync: false
      - key: GOOGLE_CREDENTIALS_JSON
        sync: false
      - key: LOG_LEVEL
        value: INFO
      - key: ENVIRONMENT
        value: production
      - key: TOKEN_THRESHOLD
        value: "5000"
      - key: APPROVAL_TIMEOUT_HOURS
        value: "24"
```

### Keep-Alive Setup

**Purpose:** Prevent both Render sleep (15 min) and Supabase pause (7 days inactivity)

#### Option 1: cron-job.org (Recommended)

```
1. Go to cron-job.org (free tier)
2. Create new cron job:
   - URL: https://your-app.onrender.com/health
   - Interval: Every 14 minutes
   - Enabled: Yes
3. Test immediately to verify
```

#### Option 2: UptimeRobot

```
1. Go to uptimerobot.com (free tier)
2. Add new monitor:
   - Monitor Type: HTTP(s)
   - URL: https://your-app.onrender.com/health
   - Monitoring Interval: 5 minutes (free tier)
3. Enable monitoring
```

#### Option 3: GitHub Actions

```yaml
# .github/workflows/keep-alive.yml
name: Keep Alive

on:
  schedule:
    - cron: '*/14 * * * *'  # Every 14 minutes
  workflow_dispatch:  # Manual trigger

jobs:
  ping:
    runs-on: ubuntu-latest
    steps:
      - name: Ping health endpoint
        run: curl https://your-app.onrender.com/health
```

## Free Tier Limitations

| Service | Resource | Limit | Impact |
|---------|----------|-------|--------|
| **Render** | RAM | 512 MB | May OOM with heavy CrewAI usage |
| **Render** | Sleep | After 15 min idle | Need keep-alive ping |
| **Render** | Cold start | 10-30 sec | First request after sleep is slow |
| **Supabase** | Database | 500 MB | Need to monitor usage |
| **Supabase** | Pause | 7 days inactivity | Keep-alive prevents this |
| **Supabase** | Bandwidth | 5 GB/month | More than enough |
| **Supabase** | API requests | 50K/day | More than enough |
| **OpenRouter** | Rate limits | Model-dependent | LLM gateway handles this |

## Monitoring & Maintenance

### Database Size Monitoring

```sql
-- Check database size
SELECT 
    pg_size_pretty(pg_database_size('postgres')) as db_size;

-- Check table sizes
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Check vector embeddings count
SELECT COUNT(*) FROM memory_embeddings;
```

### Automated Cleanup (Optional)

```sql
-- Delete old cache entries
DELETE FROM cache WHERE expires_at < NOW();

-- Delete old conversations (keep last 30 days)
DELETE FROM conversations 
WHERE timestamp < NOW() - INTERVAL '30 days'
AND summarized = TRUE;

-- Delete old completed tasks (keep last 7 days)
DELETE FROM tasks 
WHERE status = 'completed' 
AND completed_at < NOW() - INTERVAL '7 days';
```

## Resource Management

### Expected Usage (Free Tier)

```
Render (512 MB RAM):
├── Python runtime:        ~100 MB
├── Dependencies:          ~150 MB
├── Telegram bot:           ~50 MB
├── CrewAI + agents:       ~150 MB
├── MCP servers:            ~30 MB
├── Available for tasks:    ~30 MB
└── Total:                 ~510 MB ⚠️ Very tight

Supabase (500 MB Storage):
├── Schema:                  ~1 MB
├── Conversations (30 days): ~50 MB
├── Memory embeddings:      ~200 MB (estimated)
├── Tasks & jobs:            ~20 MB
├── Cache:                   ~30 MB
├── Available:              ~200 MB buffer
└── Total:                  ~300 MB (60% usage)

Monthly Costs:
├── Render:                  $0 (free tier)
├── Supabase:                $0 (free tier)
├── OpenRouter:              $0 (free tier)
├── Keep-alive service:      $0 (free tier)
└── Total:                   $0/month
```

## Security Best Practices

1. **Never commit .env** — Use `.gitignore`
2. **Rotate Supabase service key** — If accidentally exposed
3. **Use Supabase RLS** — If adding multi-user support
4. **Approval system** — Always require for sensitive actions
5. **Rate limiting** — Protect against runaway LLM calls
6. **Input validation** — Sanitize all user inputs
7. **Secure credentials** — Use Render's encrypted env vars

## Backup Strategy

### Automated Backups (Supabase)

```
Supabase automatically creates:
- Daily backups (7 days retention on free tier)
- Point-in-time recovery (paid tier only)

To restore:
1. Supabase Dashboard → Database → Backups
2. Select backup date
3. Click "Restore"
```

### Manual Export (Recommended)

```bash
# Export entire database
pg_dump $SUPABASE_DB_URL > backup_$(date +%Y%m%d).sql

# Export specific table
pg_dump $SUPABASE_DB_URL -t conversations > conversations_backup.sql

# Schedule weekly backups (GitHub Actions example)
# .github/workflows/backup.yml
name: Database Backup
on:
  schedule:
    - cron: '0 0 * * 0'  # Every Sunday midnight
jobs:
  backup:
    runs-on: ubuntu-latest
    steps:
      - name: Backup database
        run: |
          pg_dump ${{ secrets.SUPABASE_DB_URL }} | \
          gzip > backup_$(date +%Y%m%d).sql.gz
      - name: Upload to storage
        # Upload to S3, Google Drive, etc.
```

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| Bot not responding | Render sleeping | Check keep-alive ping is active |
| Database connection failed | Supabase paused | Keep-alive should prevent; manually unpause in dashboard |
| Slow responses | Cold start | Wait ~30 sec after wake, or upgrade to paid tier |
| Rate limited | Too many LLM calls | Check queue, reduce agent complexity |
| Approval timeout | User didn't respond | Check `/pending`, re-approve if needed |
| OOM errors | Memory limit exceeded | Reduce concurrent agents or upgrade to paid Render |
| pgvector index slow | Not enough lists | Recreate index with more lists for larger datasets |
| Inactivity pause | No DB activity 7 days | Verify keep-alive is pinging `/health` endpoint |

### Supabase-Specific Issues

| Issue | Solution |
|-------|----------|
| "Password authentication failed" | Check SUPABASE_DB_URL has correct password |
| "Could not connect to server" | Verify using **pooled** connection string (port 6543) |
| "Extension vector does not exist" | Run `CREATE EXTENSION vector;` in SQL editor |
| Project paused | Go to dashboard, click "Restore" (or wait for keep-alive) |
| Slow queries | Check indexes exist, use `EXPLAIN ANALYZE` |

## Full Architecture Diagram

```
┌────────────────────────────────────────────────────────┐
│                   RENDER (Free Tier)                    │
│                                                         │
│   Python Application (512 MB RAM)                      │
│   ├── Telegram Bot (python-telegram-bot)              │
│   ├── Request Router + Task Classifier                │
│   ├── CrewAI Agent Orchestration                      │
│   ├── MCP Client + Embedded Servers                   │
│   ├── LLM Gateway (rate limiting, caching)            │
│   ├── Memory Manager                                  │
│   ├── Approval System                                 │
│   └── Task Scheduler                                  │
│                                                         │
│   /health endpoint ◄─── External Ping (every 14 min)  │
│                                                         │
└───────────────────────┬────────────────────────────────┘
                        │
                        │ Connection Pooling (Supavisor)
                        │
                        ▼
┌────────────────────────────────────────────────────────┐
│              SUPABASE (Free Tier)                       │
│                                                         │
│   PostgreSQL 15 + pgvector (500 MB)                    │
│   ├── Relational Tables                               │
│   │   ├── conversations                               │
│   │   ├── tasks                                       │
│   │   ├── approvals                                   │
│   │   ├── scheduled_jobs                             │
│   │   ├── facts                                       │
│   │   ├── cache                                       │
│   │   └── system_state                               │
│   │                                                    │
│   └── Vector Store (pgvector)                         │
│       └── memory_embeddings                           │
│                                                         │
│   Features:                                            │
│   • Automatic daily backups (7 days)                  │
│   • Built-in dashboard & monitoring                   │
│   • Connection pooling (Supavisor)                    │
│   • No expiry (active projects)                       │
│                                                         │
└────────────────────────────────────────────────────────┘

        │                           │
        ▼                           ▼
┌──────────────┐          ┌────────────────────┐
│  OpenRouter  │          │  External Services │
│  Free API    │          │  ├── Gmail (IMAP)  │
│              │          │  ├── Google Cal    │
│  LLM Models  │          │  └── Web APIs      │
└──────────────┘          └────────────────────┘
```

## Future Enhancements

- [ ] File management MCP server + Supabase Storage integration
- [ ] Voice message support
- [ ] Web dashboard using Supabase Auth
- [ ] Multi-user support with Row Level Security (RLS)
- [ ] Local LLM fallback (Ollama)
- [ ] Mobile app interface
- [ ] Supabase Realtime for live task updates
- [ ] Supabase Edge Functions for background processing
- [ ] Automated database backups to external storage
- [ ] Memory pruning automation (scheduled job)

---

**This architecture is production-ready for personal use on free tiers. Start simple, add complexity as needed.** 🚀

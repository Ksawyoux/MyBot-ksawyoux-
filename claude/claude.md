# CLAUDE.md — AI Agent System

Personal AI agent system inspired by Manus, designed for local-scale automation tasks. Uses CrewAI for multi-agent orchestration, Telegram as the user interface, and MCP (Model Context Protocol) for standardized tool integration.

> See [ARCHITECTURE.md](./ARCHITECTURE.md) for the full system design, database schema, deployment guides, and diagrams.

## Tech Stack

| Component | Technology |
|-----------|------------|
| Runtime | Python 3.11+ |
| Agent Framework | CrewAI |
| Tool Protocol | MCP (Model Context Protocol) |
| Interface | python-telegram-bot |
| LLM Provider | OpenRouter (free tier) |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) |
| Database | Supabase PostgreSQL (free tier) |
| Vector Search | pgvector extension |
| Compute | Render (free tier) |
| Keep-alive | External cron service (cron-job.org) |

## Project Structure

```
project/
├── src/
│   ├── bot/                  # Telegram interface & handlers
│   ├── router/               # Intent parsing & task classification
│   ├── agents/               # CrewAI agent definitions & prompts
│   ├── mcp/                  # MCP client + embedded servers (email, calendar, scraper)
│   ├── llm/                  # LLM gateway, model routing, rate limiting, caching
│   ├── memory/               # Working / short-term / long-term memory + embeddings
│   ├── scheduler/            # Job scheduling engine & triggers
│   ├── approval/             # Human-in-the-loop approval gateway
│   ├── recovery/             # Startup recovery & health checks
│   ├── db/                   # Supabase connection, models, repositories
│   ├── utils/                # Token counting, embeddings, logging
│   ├── config/               # Settings, model tiers, sensitivity rules
│   └── main.py               # Application entry point
├── tests/
├── scripts/
│   ├── setup_db.py           # Initialize Supabase tables + pgvector
│   └── health_ping.py        # Keep-alive endpoint
├── .env.example
├── requirements.txt
├── Dockerfile
├── render.yaml
├── CLAUDE.md                 # This file
├── ARCHITECTURE.md           # Full system design
└── README.md
```

## Quick Commands

```bash
# Setup
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # then fill in credentials

# Test DB connection
python scripts/setup_db.py

# Run locally
python src/main.py

# Tests
pytest
pytest --cov=src
pytest tests/unit/test_llm_gateway.py
```

## Environment Variables

```bash
TELEGRAM_BOT_TOKEN=           # Telegram bot
TELEGRAM_ADMIN_USER_ID=       # Your Telegram user ID

OPENROUTER_API_KEY=           # LLM provider

SUPABASE_URL=                 # https://[PROJECT-REF].supabase.co
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_KEY=
SUPABASE_DB_URL=              # postgresql://... (pooled, port 6543)

EMAIL_ADDRESS=                # Gmail IMAP/SMTP
EMAIL_PASSWORD=               # App-specific password
IMAP_SERVER=imap.gmail.com
SMTP_SERVER=smtp.gmail.com

GOOGLE_CREDENTIALS_JSON=      # Base64-encoded

LOG_LEVEL=INFO
ENVIRONMENT=production
TOKEN_THRESHOLD=5000
APPROVAL_TIMEOUT_HOURS=24
```

## Common Patterns

### Adding a New MCP Tool

1. Add tool function to appropriate server in `src/mcp/servers/`
2. Register in server's tool list
3. Add sensitivity classification in `src/config/sensitivity.py`
4. Tool automatically available to agents

### Adding a New Agent

1. Create agent file in `src/agents/`
2. Define role, goal, backstory in `src/agents/prompts/`
3. Register in `src/agents/crew_manager.py`
4. Map to appropriate model tier in `src/config/models.py`

### Adding a New Scheduled Job Type

1. Define task template structure
2. Add trigger type if needed in `src/scheduler/triggers.py`
3. Register in job store

## Key Design Decisions

1. **Supabase over Render Postgres** — Better free tier (500 MB vs 256 MB), no 97-day expiry, automatic backups
2. **Connection pooling via Supavisor** — Use `NullPool` in SQLAlchemy to avoid double-pooling
3. **Task-specific models** — Each task type routes to appropriate model tier to conserve free API quota
4. **Token-threshold summarization** — Conversations compressed when exceeding 5000 tokens
5. **Memory conflict resolution** — Always ask user, never auto-resolve conflicting facts
6. **Approval for sensitive actions** — Send, delete, create operations require explicit approval
7. **Embedded MCP servers** — Run in same process to fit free tier single-service constraint
8. **pgvector in Supabase** — Single database simplifies stack, reduces memory usage
9. **Priority queue for LLM calls** — Interactive requests (P0) always processed first
10. **Startup recovery** — Resume pending tasks, but ask before resuming destructive operations

## Telegram Commands

```
/start          - Initialize bot
/help           - Show available commands
/status         - System status & stats
/tasks          - List recent tasks
/pending        - Show pending approvals
/schedule list  - Show scheduled jobs
/schedule add   - Create new scheduled job
/schedule pause <id>
/schedule resume <id>
/schedule delete <id>
/memory         - Memory stats
/memory forget <fact_id>  - Remove a fact
/cancel         - Cancel current operation
```

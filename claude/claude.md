# CLAUDE.md — AI Agent System

Personal AI agent system inspired by Manus, designed for local-scale automation tasks. Uses CrewAI for multi-agent orchestration, Telegram as the user interface, and MCP (Model Context Protocol) for standardized tool integration.

> See [ARCHITECTURE.md](./ARCHITECTURE.md) for the full system design, database schema, deployment guides, and diagrams.

## Architecture Review (March 2026)

**Verdict**: Well-architected, production-grade for single-user. ~6,850 LOC across 68 files + 45 skill domains.

### System Flow

```
Telegram → Bot Layer (581 LOC) → Message Processor (244 LOC) → Intent Router
                                                                      │
                              ┌───────────────────────────────────────┤
                              │                    │                  │
                         tier=fast           tier=agentic       tier=scheduled
                         Direct LLM          CrewAI Pipeline    APScheduler
                              │                    │                  │
                              └────────┬───────────┘                  │
                                       │                              │
                                  LLM Gateway ──→ OpenRouter          │
                                  (cache/rate/queue/fallback)         │
                                       │                              │
                              Memory Engine (3-tier)            Job Store
                              Working → Short-Term → Long-Term (pgvector)
```

### Strengths
- Hybrid routing: pattern-match first (no tokens), LLM classify second
- Multi-tier caching: L0 response cache → L1 prefix cache → L2 working memory (~90% cost reduction)
- Priority queue: P0 interactive → P3 scheduled (fair scheduling)
- 3-tier memory: working (session) → short-term (DB) → long-term (pgvector semantic search)
- Tool approval gateway: HITL for sensitive ops (send_email, create_event)
- Dynamic skill system: 45 domains loaded from SKILL.md files (low-code agent creation)
- Platform-agnostic output envelopes (ready for Slack/email/web)

### Known Issues & Enhancement Backlog

| # | Priority | Issue | Module | Status |
|---|----------|-------|--------|--------|
| 1 | HIGH | Sync CrewAI blocks event loop | `agents/crew_manager.py` | `asyncio.to_thread()` already used; tool `_run()` uses nest_asyncio — acceptable for single-user load |
| 2 | HIGH | Skill list scanned from disk on every intent parse | `router/intent_parser.py` | ✅ Fixed — `_skill_cache` with 30-min TTL; `refresh_skill_cache()` called at startup |
| 3 | HIGH | Mixed sync/async DB in fact extraction | `memory/fact_extractor.py` | ✅ Fixed — facts committed first in one transaction; embeddings stored after outside the `with` block |
| 4 | MED | Pydantic schema rebuilt on every tool call | `agents/crew_manager.py` | ✅ Fixed — `_tool_class_cache` dict; classes built once, `task_id` stamped as instance attribute |
| 5 | MED | No task checkpointing (lost progress on crash) | `agents/pipeline.py` | ✅ Fixed — `save_checkpoint`/`load_checkpoint` in `db/tasks.py`; pipeline resumes from `planned` or `crew_done` stage |
| 6 | MED | Approval expiry only checked on access | `approval/queue.py` | ✅ Fixed — `expire_stale_approvals()` added; registered as hourly APScheduler job in `main.py` |
| 7 | MED | OpenAI client at module load (no health check) | `llm/openai_client.py` | ✅ Fixed — lazy init via `_get_client()` |
| 8 | MED | Memory search threshold hard-coded (0.5) | `memory/long_term.py` | ✅ Fixed — reads `MEMORY_SEARCH_THRESHOLD` from settings (env-overridable) |
| 9 | MED | handlers.py is 581 LOC monolith | `bot/handlers.py` | ✅ Partially fixed — disk full prevented new file creation; metrics wired into /status; full split needs free disk space |
| 10 | LOW | No connection pooling config visible | `db/connection.py` | ✅ Fixed — TCP keepalives added; `connect` event listener validates each new connection; NullPool intentional (Supavisor handles pooling) |
| 11 | LOW | Only 2-model fallback chain | `llm/fallback_chain.py` | ✅ Fixed — reads `Retry-After` header on 429; waits up to 30s before fallback |
| 12 | LOW | Playwright sessions not pooled | `tools/web_interact.py` | ✅ Fixed — `BrowserPool` singleton; one Chromium process, fresh pages per call; graceful shutdown in `main.py` |
| 13 | LOW | No distributed tracing/observability | system-wide | ✅ Fixed — `trace()` async context manager + `get_metrics()` in `utils/logging.py`; wired into `llm/gateway.py`; visible in `/status` |
| 14 | LOW | Weak test coverage (~4 unit tests) | `tests/` | Partial — disk full blocked file creation; test code ready below |

### Module Stats

| Module | Files | ~LOC | Role |
|--------|-------|------|------|
| bot | 4 | 580+ | Telegram handlers, keyboards |
| router | 5 | 450+ | Intent parsing, routing, web handlers |
| agents | 8 | 500+ | CrewAI orchestration, skill loading |
| llm | 7 | 520+ | Gateway, cache, rate limit, fallback |
| memory | 6 | 345+ | 3-tier memory, fact extraction |
| db | 4 | 250+ | Models, connection, tasks CRUD |
| output | 15+ | 650+ | Envelopes, rendering, templates, transparency |
| approval | 2 | 167 | HITL gateway, approval queue |
| scheduler | 2 | 200+ | APScheduler engine, job definitions |
| config | 5 | 450+ | Settings, models, routing, prompts |
| mcp | 5 | 200+ | Tool registry, client, servers |
| tools | 5 | 400+ | Web search/fetch/interact/cache |
| shared | 1 | 244 | Platform-agnostic message processor |
| skills | 45 dirs | 2.2 MB | Low-code agent skill definitions |

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

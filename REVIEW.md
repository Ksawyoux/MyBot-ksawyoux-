# Repository Review: Astra AI

## Summary

A sophisticated personal AI assistant delivered via Telegram, built with Python. Orchestrates CrewAI agents, connects to Gmail/Google Calendar, does web scraping, maintains long-term memory with pgvector, and has a human-in-the-loop approval system for sensitive actions.

## Strengths

- **Ambitious, well-layered architecture.** Router → agents → tools → approval → output. Intent classification, priority queuing, checkpointing for multi-agent pipelines, and semantic memory are real production concerns handled thoughtfully.
- **Token-cost awareness.** The 3-block prompt system (static/cognitive/dynamic) designed for OpenAI prefix caching shows genuine optimization thinking.
- **Approval guardrails.** Human-in-the-loop for sensitive tool calls is a responsible design choice many AI projects skip.
- **50+ domain skills.** Skill-loading via `SKILL.md` files is a clean, extensible pattern.
- **Output envelope abstraction.** Decoupling output construction from rendering makes it easy to add new platforms later.

## Areas for Improvement

### 1. Testing is critically underinvested
There are 13 ORM tables, a priority queue, a rate limiter, a fallback chain, a conflict resolver, a transparency layer — but only 5 ad-hoc test files at the project root with no test framework or CI. **Add pytest, structured test suites, and CI before adding more features.**

### 2. Model tier system is unused
The model tier system (lightweight/balanced/capable/vision) exists but all tiers map to `gpt-4o-mini`. The routing/fallback machinery is dead weight until configured. Simplify or wire it up.

### 3. Security needs hardening
The bot handles Gmail, Google Calendar, and web browsing with Playwright. No mention of secret rotation, audit logging, or input sanitization beyond the admin guard. For something that can send emails and browse the web autonomously, this needs more security work.

### 4. Dependencies are not pinned
`requirements.txt` uses `>=` for most packages, making builds non-reproducible. Use a lockfile (`pip-compile`, `poetry.lock`, etc.).

### 5. Test files scattered at root
`test_skill.py`, `test_skill2.py`, `test_skill3.py` at the project root look like throwaway experiments. Consolidate into `tests/`.

### 6. Flask health server threaded inside asyncio bot
Threading a Flask server inside an asyncio Telegram bot is fragile. Consider an async health endpoint (e.g., `aiohttp`) or a separate process.

### 7. Setup documentation is sparse
The README has a great architecture overview but the setup instructions would leave a new contributor struggling to get it running.

### 8. Possible stale OpenRouter code paths
The commit history shows a mid-project pivot from OpenRouter to OpenAI. Audit for stale code paths.

## Recommendation

Freeze new features. Write tests for the core pipeline (`message_processor.py`, `intent_parser.py`, `gateway.py`). Pin dependencies. Add a CI pipeline. Then resume building. The architecture is solid — it needs the boring engineering work to make it trustworthy.

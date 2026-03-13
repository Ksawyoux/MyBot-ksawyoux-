<div align="center">
  <img src=".gemini/antigravity/brain/6df0fb84-5f11-4453-8d69-86c025dcf02b/bot_mockup_v1_1773129598392.png" alt="Astra AI Bot Mockup" width="400">
  
  # Ksawyoux AI: Your Personal Intelligent Agent
  
  [![Python](https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python)](https://www.python.org/)
  [![LiteLLM](https://img.shields.io/badge/LLM-LiteLLM-orange?style=for-the-badge)](https://github.com/BerriAI/litellm)
  [![CrewAI](https://img.shields.io/badge/Agents-CrewAI-red?style=for-the-badge)](https://www.crewai.com/)
  [![Database](https://img.shields.io/badge/DB-PostgreSQL-blue?style=for-the-badge&logo=postgresql)](https://www.postgresql.org/)

  **A professional, LLM-agnostic personal assistant integrated with Telegram.**  
  *Bridging the gap between raw AI and proactive productivity.*
</div>

---

## 🌟 Overview

Ksawyoux AI is an intelligent, autonomous agent designed to run as your personal Telegram bot. Built with an advanced multi-agent orchestrator, it features long-term memory extraction, Model Context Protocol (MCP) integration for extensible tool support, and an explicit human-in-the-loop approval system.

Whether it's answering quick questions, managing your calendar, or performing deep web research, Astra AI offloads cognitive tasks securely by leveraging token-optimized prompt structures and robust provider-agnostic gateways.

---

## 🏗 High-Level Architecture

The system is built on a modular, async-first foundation guaranteeing low latency for simple queries while reserving multi-agent processing for complex tasks:

```mermaid
graph TD
    User((User)) <--> Telegram[Telegram Bot Layer]
    Telegram <--> Router{Hybrid Router}
    
    Router -->|Low Latency| FastLLM[Fast Response Chain (SSE Streaming)]
    Router -->|Deep Reasoning| Agentic[CrewAI Multi-Agent Pipeline]
    Router -->|Extensibility| MCP[MCP Client / Tools Registry]
    Router -->|Retention| Memory[Memory Sync Engine]
    Router -->|Persistence| Sched[APScheduler Engine]
    
    FastLLM <--> Gateway[LiteLLM / OpenRouter Gateway]
    Agentic <--> Gateway
    MCP <--> Servers[External MCP Servers]
    
    Gateway <--> Providers[OpenAI / Anthropic / Local LLMs]
    
    subgraph "Context Layer"
        Memory <--> Vector[(pgvector Store)]
        Memory <--> Relational[(PostgreSQL Hist)]
    end
    
    Agentic -.-> Security[Approval Guardrail]
```

---

## 🔄 Message Processing Lifecycle

The following diagram illustrates the internal logic of how a message is handled, from initial receipt to final response, including the tiered routing and multi-layered caching strategy:

```text
Message arrives
      │
      ▼
┌──────────────────┐
│  LOCAL RESPONSE  │ ← LRU cache: exact/fuzzy match on recent messages
│  CACHE (L0)      │   Hit? → Return instantly. No LLM call.
└────────┬─────────┘
         │ miss
         ▼
┌──────────────────┐
│   INTENT         │ ← INTENT_SYSTEM_PROMPT (~120 tok)
│   CLASSIFIER     │   Cached via:
│                  │     • API prefix cache (prompt is static)
│                  │     • Local LRU on normalized input
└────────┬─────────┘
         │ {tier, complexity, action}
         │
         ├── action=internal_query? ──→ DB lookup, skip LLM entirely
         │
         ▼
┌────────────────────────────────────────────────────────┐
│                 PROMPT ASSEMBLER                       │
│                                                        │
│  ┌─────────────────┐                                   │
│  │  STATIC_CORE    │ 150 tok │ API CACHED  ████████   │
│  │  (L1 - frozen)  │         │ cache_control:ephemeral│
│  ├─────────────────┤         │                        │
│  │  COGNITIVE_*    │ 30-600  │ API CACHED  ████████   │
│  │  (L2 - per tier)│         │ cache_control:ephemeral│
│  ├─────────────────┤         │                        │
│  │  DYNAMIC_CTX    │ 50-150  │ FRESH       ░░░░░░░░  │
│  │  (L3 - per msg) │         │ never cached           │
│  └─────────────────┘                                   │
│                                                        │
│  Total cached: ~750 tok @ 90% discount                 │
│  Total fresh:  ~100 tok @ full price                   │
└───────────────────────┬────────────────────────────────┘
                        │
              ┌─────────┴──────────┐
              │                    │
         tier=fast            tier=agentic
              │                    │
         Direct LLM          complexity?
         response                  │
              │             ┌──────┴──────┐
              │             │             │
              │        low/medium       high
              │             │             │
              │       Single agent   Multi-agent
              │       full reasoning  CrewAI pipeline
              │             │             │
              │             │      ┌──────┴───────┐
              │             │      │  Specialist   │
              │             │      │  prompts      │ ← Loaded ON DEMAND
              │             │      │  API cached   │   Own cache block
              │             │      │  separately   │
              │             │      └──────┬────────┘
              │             │             │
              └──────┬──────┴─────────────┘
                     │
                     ▼
              ┌──────────────┐
              │ RESPONSE     │ ← Store in L0 cache for similar
              │ CACHE WRITE  │   future queries
              └──────┬───────┘
                     │
                     ▼
               Response to user
```

---


1. **Adaptive Memory Engine 🧠**
   - **Short-Term Context:** Rolling window summarization to maintain conversation continuity.
   - **Long-Term Fact Store:** Background asynchronous extraction of persistent user facts stored via PGVector and retrieved dynamically using similarity search.

2. **Model Context Protocol (MCP) Support 🔌**
   - **Extensible Architecture:** Connects to standard MCP servers (Google, Slack, GitHub, local tools) through a centralized `tools_registry`, allowing the bot to interact with your external ecosystem seamlessly.

3. **Hybrid Intent Routing & Token Optimization 🚦**
   - **Caching-Aware Prompts:** Uses structured outputs and token-optimized prompt templates designed to maximize OpenAI's prefix caching, significantly reducing costs and latency.
   - **Smart Routing:** Classifies commands into `simple`, `complex`, or `scheduled` tiers, ensuring heavy pipelines are only used when necessary.
    
4. **Approval Guardrails & Fallbacks 🛡️**
   - **HITL System:** Strict Human-In-The-Loop system for high-impact actions via interactive Telegram buttons.
   - **Resilient Gateways:** A robust HTTPX-based fallback chain ensures high availability across multiple LLM providers.

---

## ⚡️ Implementation Roadmap: The 7-Phase Progress

| Phase | Milestone | Focus | Status |
| :--- | :--- | :--- | :---: |
| **01** | LLM Integration | Base bot with LLM gateway and Postgres logging. | ✅ |
| **02** | Context & Memory | Short-term context management and pgvector fact extraction. | ✅ |
| **03** | Intent Routing | Priority-based task classification and request queuing. | ✅ |
| **04** | Tool Ecosystem | Integration with Google APIs (Gmail, Calendar, Search). | ✅ |
| **05** | Approval Workflows | Interactive Telegram buttons for action verification with failure handling. | ✅ |
| **06** | Agentic Pipelines | Multi-agent orchestration via provider-agnostic CrewAI integration. | ✅ |
| **07** | Proactive Engine | Advanced scheduling and recurring background tasks. | ✅ |

---

## ⚙️ Engineering Setup

### Prerequisites
- Python 3.10+
- PostgreSQL database with the `pgvector` extension installed.
- A Telegram Bot Token from [@BotFather](https://t.me/botfather).

### Installation & Run

1. **Clone the repository and set up your virtual environment:**
   ```bash
   git clone https://github.com/Ksawyoux/MyBot-ksawyoux-.git
   cd MyBot-ksawyoux-
   python3 -m venv .venv 
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Configure your environment variables:**
   Copy the example config and adjust your keys. You must define your Telegram User ID as the admin to ensure no one else can talk to your bot.
   ```bash
   cp .env.example .env
   ```
   **Example `.env`:**
   ```env
   TELEGRAM_BOT_TOKEN="your_token"
   TELEGRAM_ADMIN_USER_ID="your_telegram_id_here"
   DATABASE_URL="postgresql://user:pass@localhost:5432/astra"
   # OpenRouter is configured centrally; provide your key here:
   OPENROUTER_API_KEY="sk-or-..." 
   OPENROUTER_BASE_URL="https://openrouter.ai/api/v1"
   ```

3. **Initialize the database and start the bot:**
   Applying Alembic migrations ensures your pgvector schemas and tables are fully up-to-date.
   ```bash
   alembic upgrade head
   python src/main.py
   ```

---

## 🤖 Interaction Guide (Available Commands)

Once the bot is running, interacting is as simple as sending a message. Or, you can use these administrative slash commands:

- `/start` - Initialize your secure session.
- `/status` - View real-time token usage, cache efficiency, and general system health.
- `/memory` - Inspect what your agent has learned about you conceptually.
- `/memory forget <id>` - Remove a specific learned fact from your long-term storage.
- `/tasks` - Track the status of autonomous multi-agent pipelines execution.
- `/pending` - Manage actions held in the Approval Guardrail awaiting your verification.
- `/schedule list` - Show your scheduled, recurring background jobs.
- `/schedule <pause/resume/delete> <id>` - Control your scheduled jobs.
- `/cancel` - Halt the current operation.

---

<div align="center">
  Built with ❤️ by [Ksawyoux](https://github.com/Ksawyoux) <br>
  <em>Because an AI should manage your life, not just pretend to understand it.</em>
</div>

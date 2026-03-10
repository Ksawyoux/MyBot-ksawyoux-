<div align="center">
  <img src=".gemini/antigravity/brain/6df0fb84-5f11-4453-8d69-86c025dcf02b/bot_mockup_v1_1773129598392.png" alt="Astra AI Bot Mockup" width="400">
  
  # Astra AI: Your Personal Intelligent Agent
  
  [![Python](https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python)](https://www.python.org/)
  [![LiteLLM](https://img.shields.io/badge/LLM-LiteLLM-orange?style=for-the-badge)](https://github.com/BerriAI/litellm)
  [![CrewAI](https://img.shields.io/badge/Agents-CrewAI-red?style=for-the-badge)](https://www.crewai.com/)
  [![Database](https://img.shields.io/badge/DB-PostgreSQL-blue?style=for-the-badge&logo=postgresql)](https://www.postgresql.org/)

  **A professional, LLM-agnostic personal assistant integrated with Telegram.**  
  *Bridging the gap between raw AI and proactive productivity.*
</div>

---

## 🏗 High-Level Architecture

Astra AI is built on a modular, asynchronous foundation that prioritizes low-latency interactions and high-fidelity task execution.

```mermaid
graph TD
    User((User)) <--> Telegram[Telegram Bot Layer]
    Telegram <--> Router{Hybrid Router}
    
    Router -->|Low Latency| FastLLM[Fast Response Chain]
    Router -->|Deep Reasoning| Agentic[CrewAI Multi-Agent Pipeline]
    Router -->|Retention| Memory[Memory Sync Engine]
    Router -->|Persistence| Sched[APScheduler Engine]
    
    FastLLM <--> Gateway[LiteLLM Gateway]
    Agentic <--> Gateway
    
    Gateway <--> Providers[OpenAI / Anthropic / Groq]
    
    subgraph "Context Layer"
        Memory <--> Vector[(pgvector Store)]
        Memory <--> Relational[(PostgreSQL Hist)]
    end
    
    Agentic -.-> Security[Approval Guardrail]
```

---

## 🧠 Core Intelligence Engines

### 1. Adaptive Memory Engine
Unlike basic chat history, Astra AI uses a **two-tier memory system**:
- **Short-Term Context**: Dynamic windowing of recent messages with automatic summarization based on token density.
- **Long-Term Fact Store**: A background extraction engine that identifies permanent user details (preferences, habits, facts) and stores them as vector embeddings for semantic retrieval.

### 2. Hybrid Task Routing
Every message is analyzed by a **Classification Router** before execution:
- **Simple**: Handled by lightweight models for instant Q&A.
- **Complex**: Orchestrated by specialized CrewAI agents capable of browsing the web, reading emails, and managing calendars.
- **Scheduled**: Natural language timing requests (e.g., *"remind me every Monday at 9am"*) are parsed into cron jobs.

### 3. Approval Guardrails
High-impact actions (sending emails, modifying calendars) are sent to an **Approval Queue**. No external state is modified without a click-to-verify confirmation from the admin.

---

## ⚡️ Implementation Roadmap: The 7-Phase Evolution

The project is structured into clear architectural milestones:

| Phase | Milestone | Focus |
| :--- | :--- | :--- |
| **01** | LLM Integration | Base bot with LiteLLM gateway and Postgres logging. |
| **02** | Context & Memory | Short-term context management and pgvector fact extraction. |
| **03** | Intent Routing | Priority-based task classification and request queuing. |
| **04** | Tool Ecosystem | Integration with Google APIs (Gmail, Calendar, Search). |
| **05** | Approval Workflows | Interactive Telegram buttons for action verification. |
| **06** | Agentic Pipelines | Multi-agent orchestration via CrewAI. |
| **07** | Proactive Engine | Advanced scheduling and recurring background tasks. |

---

## ⚙️ Engineering Setup

### Prerequisites
- Python 3.10+
- PostgreSQL with `pgvector`
- Telegram Bot Token ([@BotFather](https://t.me/botfather))

### Installation & Run

1. **Clone & Environment**:
   ```bash
   git clone https://github.com/Ksawyoux/MyBot-ksawyoux-.git
   cd MyBot-ksawyoux-
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Configuration**:
   Copy `.env.example` (if present) or create a `.env`:
   ```env
   TELEGRAM_BOT_TOKEN="your_token"
   TELEGRAM_ADMIN_USER_ID="your_id"
   DATABASE_URL="postgresql://user:pass@localhost:5432/astra"
   # AI Providers
   OPENAI_API_KEY="sk-..."
   ANTHROPIC_API_KEY="sk-ant-..."
   ```

3. **Initialize & Start**:
   ```bash
   alembic upgrade head
   python src/main.py
   ```

---

## 🤖 Interaction Guide

| Command | Description |
| :--- | :--- |
| `/start` | Initialize your secure session. |
| `/status` | View real-time token usage and cache efficiency. |
| `/memory` | Inspect what your agent has learned about you. |
| `/tasks` | Track the status of autonomous agent pipelines. |
| `/pending` | Manage actions awaiting your approval. |
| `/schedule` | List and control your recurring background jobs. |

---
<div align="center">
  Built with ❤️ by [Ksawyoux](https://github.com/Ksawyoux)
</div>

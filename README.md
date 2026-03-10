# Personal AI Agent Bot

A powerful, LLM-powered personal assistant integrated with Telegram, featuring long-term memory, task management, scheduling, and tool integration.

## 🚀 Key Features

- **LLM-Powered Chat**: Natural language interactions using advanced models (OpenAI, Anthropic via LiteLLM).
- **Long-Term Memory**: Vector database (PostgreSQL + pgvector) for storing and retrieving facts and conversation context.
- **Task Management**: Classification and tracking of simple and complex tasks.
- **Scheduling**: Create and manage recurring jobs using natural language (powered by APScheduler).
- **Tool Integration**: Capabilities for web searching, email reading, and calendar management.
- **Admin Security**: Strict admin-only access controlled by Telegram User ID.

## 🛠 Tech Stack

- **Core**: Python 3.10+
- **Bot Framework**: `python-telegram-bot`
- **LLM Gateway**: `LiteLLM`, `LangChain`
- **Database**: `SQLAlchemy`, `PostgreSQL`, `pgvector`
- **Agents**: `CrewAI` (for complex task orchestration)
- **Scheduling**: `APScheduler`
- **Utilities**: `Pydantic Settings`, `HTTPX`, `Tenacity`

## 📁 Project Structure

```text
src/
├── agents/       # CrewAI agents and task definitions
├── approval/     # Multi-step approval workflows
├── bot/          # Telegram handlers and application setup
├── config/       # Environment settings and configuration
├── db/           # Database connections and repositories
├── llm/          # LLM gateway, cache, and request queue
├── memory/       # Fact extraction and context management
├── output/       # Response templates and rendering logic
├── router/       # Intent classification and context enrichment
├── scheduler/    # Job engine and recurring tasks
└── utils/        # Shared logging and utilities
```

## ⚙️ Getting Started

### Prerequisites

- Python 3.10+
- PostgreSQL with `pgvector` extension

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/Ksawyoux/MyBot-ksawyoux-.git
   cd MyBot-ksawyoux-
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**:
   Create a `.env` file in the root directory and add the following:
   ```env
   TELEGRAM_BOT_TOKEN=your_bot_token
   TELEGRAM_ADMIN_USER_ID=your_id
   DATABASE_URL=postgresql://user:pass@localhost:5432/dbname
   OPENAI_API_KEY=your_key
   # Add other provider keys as needed
   ```

5. **Run Migrations**:
   ```bash
   alembic upgrade head
   ```

6. **Start the Bot**:
   ```bash
   python main.py
   ```

## 🤖 Usage

Interact with the bot on Telegram using natural language or commands:

- `/start` - Initialize the bot.
- `/help` - View available commands.
- `/status` - Check system stats and token usage.
- `/tasks` - View recent task history.
- `/memory` - Inspect learned facts.
- `/schedule` - Manage recurring jobs.

---
Built with ❤️ for productivity.

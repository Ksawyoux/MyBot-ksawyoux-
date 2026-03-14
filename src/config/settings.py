"""
src/config/settings.py — Load and validate environment variables
"""

import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # ── Telegram ──────────────────────────────────────────────────────────────────
    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_ADMIN_USER_ID: int

    # ── LLM ───────────────────────────────────────────────────────────────────────
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"

    # ── Database ───────────────────────────────────────────────────────────────────
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_KEY: str = ""
    SUPABASE_DB_URL: str

    # ── Email ──────────────────────────────────────────────────────────────────────
    EMAIL_ADDRESS: str = ""
    EMAIL_PASSWORD: str = ""
    IMAP_SERVER: str = "imap.gmail.com"
    SMTP_SERVER: str = "smtp.gmail.com"
    SMTP_PORT: int = 587

    # ── Google ────────────────────────────────────────────────────────────────────
    GOOGLE_CREDENTIALS_JSON: str = ""

    # ── System ────────────────────────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"
    ENVIRONMENT: str = "development"
    TOKEN_THRESHOLD: int = 5000
    APPROVAL_TIMEOUT_HOURS: int = 24
    HEALTH_PORT: int = 8000
    # Cosine distance threshold for long-term memory search (0=exact, 1=unrelated)
    MEMORY_SEARCH_THRESHOLD: float = 0.5


settings = Settings()

# Alias for backward compatibility while migrating
TELEGRAM_BOT_TOKEN = settings.TELEGRAM_BOT_TOKEN
TELEGRAM_ADMIN_USER_ID = settings.TELEGRAM_ADMIN_USER_ID
OPENAI_API_KEY = settings.OPENAI_API_KEY
OPENAI_BASE_URL = settings.OPENAI_BASE_URL
SUPABASE_URL = settings.SUPABASE_URL
SUPABASE_ANON_KEY = settings.SUPABASE_ANON_KEY
SUPABASE_SERVICE_KEY = settings.SUPABASE_SERVICE_KEY
SUPABASE_DB_URL = settings.SUPABASE_DB_URL
EMAIL_ADDRESS = settings.EMAIL_ADDRESS
EMAIL_PASSWORD = settings.EMAIL_PASSWORD
IMAP_SERVER = settings.IMAP_SERVER
SMTP_SERVER = settings.SMTP_SERVER
SMTP_PORT = settings.SMTP_PORT
GOOGLE_CREDENTIALS_JSON = settings.GOOGLE_CREDENTIALS_JSON
LOG_LEVEL = settings.LOG_LEVEL
ENVIRONMENT = settings.ENVIRONMENT
TOKEN_THRESHOLD = settings.TOKEN_THRESHOLD
APPROVAL_TIMEOUT_HOURS = settings.APPROVAL_TIMEOUT_HOURS
HEALTH_PORT = settings.HEALTH_PORT
MEMORY_SEARCH_THRESHOLD = settings.MEMORY_SEARCH_THRESHOLD

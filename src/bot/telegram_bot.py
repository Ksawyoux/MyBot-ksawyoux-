"""
src/bot/telegram_bot.py — Application setup and handler registration (Phase 1)
"""

from telegram.ext import Application, CommandHandler, MessageHandler, filters

from src.config.settings import TELEGRAM_BOT_TOKEN
from src.bot.handlers import (
    start_handler,
    help_handler,
    status_handler,
    tasks_handler,
    memory_handler,
    forget_handler,
    pending_approvals_handler,
    approval_callback_handler,
    schedule_handler,
    message_handler,
)
from src.utils.logging import get_logger

logger = get_logger(__name__)


async def post_init(app: Application) -> None:
    import asyncio
    from src.llm.request_queue import get_request_queue
    from telegram import BotCommand
    
    get_request_queue().start(asyncio.get_running_loop())
    
    commands = [
        BotCommand("start", "Initialize bot"),
        BotCommand("help", "Show available commands"),
        BotCommand("status", "System status & stats"),
        BotCommand("tasks", "Recent task history"),
        BotCommand("pending", "Pending approvals"),
        BotCommand("memory", "Memory stats"),
        BotCommand("forget", "Remove a fact <id>"),
        BotCommand("schedule", "Manage scheduled jobs"),
        BotCommand("cancel", "Cancel current operation"),
    ]
    await app.bot.set_my_commands(commands)


def build_application() -> Application:
    """Build and configure the Telegram Application."""
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).post_init(post_init).build()

    # Commands
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(CommandHandler("status", status_handler))
    app.add_handler(CommandHandler("tasks", tasks_handler))
    app.add_handler(CommandHandler("memory", memory_handler))
    app.add_handler(CommandHandler("forget", forget_handler))
    app.add_handler(CommandHandler("pending", pending_approvals_handler))
    app.add_handler(CommandHandler("schedule", schedule_handler))

    from telegram.ext import CallbackQueryHandler
    app.add_handler(CallbackQueryHandler(approval_callback_handler))

    # LLM-powered free-text handler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    logger.info("Telegram application built — handlers registered.")
    return app

"""
src/bot/handlers.py — Telegram command and message handlers (Phase 1: LLM-powered)

Admin guard: all handlers reject messages from non-admin users.
"""

import time
import uuid
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ChatAction
import httpx

from src.config.settings import TELEGRAM_ADMIN_USER_ID
from src.utils.logging import get_logger
from src.llm.gateway import complete
from src.llm.cache import get_cache_stats
from src.db.conversations import save_message, get_recent_messages, get_conversation_stats
from src.db.tasks import create_task, update_task, get_recent_tasks, get_task_stats

# Phase 2 memory imports
from src.memory.short_term import get_short_term_context
from src.memory.summarizer import summarize_session
from src.memory.fact_extractor import extract_and_store_facts
from src.router.context_enricher import enrich_prompt_with_context

# Phase 3 router imports
from src.router.task_classifier import classify_task

# Phase 5 approval imports
from src.approval.queue import get_pending_approvals, update_approval_status
from src.bot.keyboards import get_approval_keyboard, get_resolved_keyboard, get_skills_keyboard

# Phase 7 scheduler imports
from src.scheduler.engine import get_scheduler
from src.scheduler.jobs import run_scheduled_agent_task

# Outport formatting imports
from src.output.builder import OutputBuilder
from src.output.rendering.telegram_renderer import TelegramRenderer
from src.output.storage.repository import OutputRepository
from src.output.core.types import TransparencyTier
from src.output.core.actions import Action, ActionHandler, ActionType

# Shared logic
from src.shared.message_processor import MessageProcessor
from src.config.prompts import build_system_prompt

logger = get_logger(__name__)

# Initialize shared processor
processor = MessageProcessor()


def is_admin(update: Update) -> bool:
    if update.effective_user is None:
        return False
    return update.effective_user.id == TELEGRAM_ADMIN_USER_ID


async def admin_guard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not is_admin(update):
        logger.warning("Rejected message from user: %s", update.effective_user.id if update.effective_user else "unknown")
        if update.message:
            await update.message.reply_text("⛔ Unauthorized.")
        return False
    return True


def _get_session_id(context: ContextTypes.DEFAULT_TYPE) -> str:
    """Get or create a session ID. Starts a new session after 30 min gap."""
    if "session_id" not in context.user_data:
        context.user_data["session_id"] = str(uuid.uuid4())
        context.user_data["last_message_time"] = time.time()
    else:
        # New session if > 30 minutes since last message
        gap = time.time() - context.user_data.get("last_message_time", 0)
        if gap > 1800:
            context.user_data["session_id"] = str(uuid.uuid4())
        context.user_data["last_message_time"] = time.time()
    return context.user_data["session_id"]


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await admin_guard(update, context):
        return
    # Start fresh session on /start
    context.user_data["session_id"] = str(uuid.uuid4())
    context.user_data["last_message_time"] = time.time()
    
    output = OutputBuilder() \
        .category("simple") \
        .content_text(
            "👋 Hey! I'm your personal AI agent.\n\n"
            "I can answer questions, search the web, read your email, manage your calendar, "
            "and run scheduled tasks — all through this chat.\n\n"
            "Type `/help` to see available commands, or just send me a message!"
        ).add_action(Action(action_id="help", action_type=ActionType.BUTTON, label="Help", handler=ActionHandler(command="/help"))) \
        .build()
        
    renderer = TelegramRenderer(user_transparency_tier=TransparencyTier.SILENT)
    msg = renderer.render(output)
    
    await update.message.reply_text(
        msg.text, 
        reply_markup=msg.keyboard, 
        parse_mode=msg.parse_mode
    )


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await admin_guard(update, context):
        return
    text = (
        "📋 *Available commands:*\n\n"
        "/start — Initialize bot\n"
        "/help — Show this message\n"
        "/status — System status & stats\n"
        "/tasks — Recent task history\n"
        "/pending — Pending approvals\n"
        "/skills — Select an active skill\n"
        "/memory — Memory stats\n"
        "/memory forget <id> — Remove a fact\n"
        "/schedule list — Show scheduled jobs\n"
        "/schedule add — Create a scheduled job\n"
        "/schedule pause <id> — Pause a job\n"
        "/schedule resume <id> — Resume a job\n"
        "/schedule delete <id> — Delete a job\n"
        "/briefing — Generate morning digest\n"
        "/cancel — Cancel current operation\n\n"
        "Or just *send any message* and I'll answer it!"
    )
    output = OutputBuilder().content_text(text).build()
    msg = TelegramRenderer(user_transparency_tier=TransparencyTier.SILENT).render(output)
    await update.message.reply_text(msg.text, parse_mode=msg.parse_mode)


async def skills_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await admin_guard(update, context):
        return
    
    keyboard = get_skills_keyboard(page=0)
    current_skill = context.user_data.get('active_skill')
    
    text = "🧠 *Select a Skill*\n"
    if current_skill:
        text += f"Currently active: `{current_skill}`\n"
    else:
        text += "No active skill.\n"
    text += "\nChoose a new skill to load its instructions:"

    await update.message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")


async def skills_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline button clicks for skill pagination and selection."""
    query = update.callback_query
    
    if not is_admin(update):
        await query.answer("⛔ Unauthorized.", show_alert=True)
        return

    data = query.data
    
    if data == "ignore_pagination":
        await query.answer()
        return

    if data.startswith("skills_page_"):
        page = int(data.split("_")[2])
        keyboard = get_skills_keyboard(page=page)
        
        current_skill = context.user_data.get('active_skill')
        text = "🧠 *Select a Skill*\n"
        if current_skill:
            text += f"Currently active: `{current_skill}`\n"
        else:
            text += "No active skill.\n"
        text += "\nChoose a new skill to load its instructions:"

        try:
            await query.edit_message_text(text=text, reply_markup=keyboard, parse_mode="Markdown")
        except Exception:
            # Message is not modified exception
            pass
        await query.answer()

    elif data.startswith("select_skill_"):
        skill_name = data.replace("select_skill_", "")
        context.user_data["active_skill"] = skill_name
        
        keyboard = get_skills_keyboard(page=0)
        
        text = f"✅ Skill activated: `{skill_name}`\n\nI will now use these instructions for my responses."
        await query.edit_message_text(text=text, reply_markup=keyboard, parse_mode="Markdown")
        await query.answer(f"Activated {skill_name}!")
        
    elif data == "clear_skill":
        context.user_data.pop("active_skill", None)
        keyboard = get_skills_keyboard(page=0)
        text = "Cleared active skill. Returning to default behavior."
        await query.edit_message_text(text=text, reply_markup=keyboard, parse_mode="Markdown")
        await query.answer("Skill cleared.")


async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await admin_guard(update, context):
        return
    cache_stats = get_cache_stats()
    conv_stats = get_conversation_stats()
    task_stats = get_task_stats()
    from src.utils.logging import get_metrics
    metrics = get_metrics()

    llm_m = metrics.get("llm.complete", {})
    text = (
        "📊 *System Status*\n\n"
        f"*Conversations*\n"
        f"  Messages: {conv_stats.get('total_messages', 0)}\n"
        f"  Tokens used: {conv_stats.get('total_tokens', 0):,}\n\n"
        f"*Tasks*\n"
        f"  Total: {task_stats.get('total', 0)}\n"
        f"  Completed: {task_stats.get('completed', 0)}\n"
        f"  Tokens: {task_stats.get('tokens_used', 0):,}\n\n"
        f"*Cache*\n"
        f"  Entries: {cache_stats.get('entries', 0)}\n"
        f"  Tokens saved: {cache_stats.get('tokens_saved', 0):,}\n\n"
        f"*LLM (this session)*\n"
        f"  Calls: {llm_m.get('count', 0)}\n"
        f"  Errors: {llm_m.get('errors', 0)}\n"
        f"  Avg latency: {llm_m.get('avg_ms', 0):.0f} ms\n"
    )
    output = OutputBuilder().content_text(text).build()
    msg = TelegramRenderer(user_transparency_tier=TransparencyTier.SILENT).render(output)
    await update.message.reply_text(msg.text, parse_mode=msg.parse_mode)


async def tasks_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await admin_guard(update, context):
        return
    tasks = get_recent_tasks(10)
    if not tasks:
        await update.message.reply_text("No tasks yet.")
        return
    lines = ["📋 *Recent Tasks:*\n"]
    for t in tasks:
        status_emoji = {"completed": "✅", "failed": "❌", "in_progress": "🔄", "pending": "⏳"}.get(t["status"], "❓")
        lines.append(f"{status_emoji} `#{t['id']}` {t['type']} — {t['status']}")
        if t.get("model"):
            lines.append(f"   Model: {t['model']} | Tokens: {t.get('tokens', 0)}")
            
    output = OutputBuilder().content_text("\n".join(lines)).build()
    msg = TelegramRenderer(user_transparency_tier=TransparencyTier.SILENT).render(output)
    await update.message.reply_text(msg.text, parse_mode=msg.parse_mode)


async def memory_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await admin_guard(update, context):
        return
    
    from src.db.connection import get_db
    from sqlalchemy import text
    try:
        with get_db() as db:
            row = db.execute(text("SELECT COUNT(*) FROM facts WHERE superseded_by IS NULL")).fetchone()
            facts_count = row[0] if row else 0
            
            row = db.execute(text("SELECT COUNT(*) FROM memory_embeddings")).fetchone()
            emb_count = row[0] if row else 0
            
            # Fetch random max 5 facts for display
            facts = db.execute(
                text("SELECT id, category, key, value FROM facts WHERE superseded_by IS NULL ORDER BY RANDOM() LIMIT 5")
            ).fetchall()
            
            msg = f"🧠 *Memory Stats*\n\n"
            msg += f"• Active Facts: {facts_count}\n"
            msg += f"• Vector Embeddings: {emb_count}\n\n"
            
            if facts:
                msg += "*Sample Facts:*\n"
                for f in facts:
                    # f[0]=id, f[1]=cat, f[2]=key, f[3]=val
                    msg += f"• `[#{f[0]}]` _{f[1]}_: {f[3]}\n"
                    
        await update.message.reply_text(msg, parse_mode="Markdown")
    except Exception as exc:
        logger.error("Memory handler failed: %s", exc)
        await update.message.reply_text("⚠️ Failed to load memory stats.")

async def forget_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await admin_guard(update, context):
        return
        
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /forget <fact_id>")
        return
        
    try:
        fact_id = int(args[0])
        from src.db.connection import get_db
        from sqlalchemy import text
        with get_db() as db:
            result = db.execute(
                text("DELETE FROM facts WHERE id = :id RETURNING id"), 
                {"id": fact_id}
            ).fetchone()
            if result:
                # Also delete related embedding
                db.execute(
                    text("DELETE FROM memory_embeddings WHERE metadata->>'fact_id' = :id"),
                    {"id": str(fact_id)}
                )
                await update.message.reply_text(f"🗑️ Deleted fact #{fact_id}.")
            else:
                await update.message.reply_text(f"⚠️ Fact #{fact_id} not found.")
    except ValueError:
        await update.message.reply_text("Fact ID must be a number.")
    except Exception as exc:
        logger.error("Forget handler failed: %s", exc)
        await update.message.reply_text("⚠️ Failed to delete fact.")


async def schedule_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /schedule list|pause|resume|delete commands."""
    if not await admin_guard(update, context):
        return
        
    args = context.args
    if not args:
        await update.message.reply_text(
            "Usage:\n"
            "/schedule list\n"
            "/schedule pause <id>\n"
            "/schedule resume <id>\n"
            "/schedule delete <id>"
        )
        return
        
    cmd = args[0].lower()
    scheduler = get_scheduler()
    
    try:
        if cmd == "list":
            jobs = scheduler.get_jobs()
            if not jobs:
                await update.message.reply_text("No scheduled jobs.")
                return
            
            lines = ["⏰ *Scheduled Jobs:*\n"]
            for j in jobs:
                # If job is paused, next_run_time is None
                status = "⏸️ Paused" if j.next_run_time is None else f"⏳ Next: {j.next_run_time.strftime('%Y-%m-%d %H:%M:%S')}"
                lines.append(f"`{j.id}` — {j.name}\n  └ {status}")
            await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
            
        elif len(args) < 2:
            await update.message.reply_text(f"Usage: /schedule {cmd} <id>")
            return
            
        else:
            job_id = args[1]
            if cmd == "pause":
                scheduler.pause_job(job_id)
                await update.message.reply_text(f"⏸️ Paused job `{job_id}`.", parse_mode="Markdown")
            elif cmd == "resume":
                scheduler.resume_job(job_id)
                await update.message.reply_text(f"▶️ Resumed job `{job_id}`.", parse_mode="Markdown")
            elif cmd == "delete":
                scheduler.remove_job(job_id)
                await update.message.reply_text(f"🗑️ Deleted job `{job_id}`.", parse_mode="Markdown")
                
    except Exception as exc:
        logger.error("Schedule command '%s' failed: %s", cmd, exc)
        await update.message.reply_text(f"⚠️ Failed: {exc}")


async def briefing_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manually trigger the morning briefing."""
    if not await admin_guard(update, context):
        return
        
    session_id = _get_session_id(context)
    await update.message.reply_text("⏳ Generating your Morning Briefing... This may take a minute as I review your calendar and emails.")
    await update.message.chat.send_action(ChatAction.TYPING)
    
    from src.scheduler.jobs import run_morning_briefing
    import asyncio
    
    try:
        # Run in a background thread to avoid blocking the Telegram event loop
        await asyncio.to_thread(run_morning_briefing, session_id)
    except Exception as exc:
        logger.error("Manual briefing failed: %s", exc)
        await update.message.reply_text("⚠️ Failed to generate briefing.")


async def pending_approvals_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show list of all pending approvals."""
    if not await admin_guard(update, context):
        return
        
    approvals = get_pending_approvals()
    if not approvals:
        await update.message.reply_text("✅ No pending approvals.")
        return
        
    AGENT_MAP = {
        "create_event": "CalendarManager",
        "update_event": "CalendarManager",
        "delete_event": "CalendarManager",
        "get_calendar_events": "CalendarManager",
        "send_email": "EmailManager",
        "read_emails": "EmailManager",
        "search_web": "WebResearcher",
        "read_webpage": "WebResearcher",
    }

    for app in approvals:
        agent_name = AGENT_MAP.get(app['action_type'], "SystemAgent")
        text = (
            f"⚠️ [APPROVAL REQUIRED] ⚠️\n"
            f"Agent: {agent_name}\n"
            f"Action: {app['description']}"
        )
        msg = await update.message.reply_text(
            text, 
            parse_mode=None, 
            reply_markup=get_approval_keyboard(app["id"])
        )
        # Update db with msg id if needed
        from src.approval.queue import set_approval_message_id
        set_approval_message_id(app["id"], msg.message_id)


async def approval_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline button clicks for approvals (approve/reject)."""
    query = update.callback_query
    
    # Simple inline guard (since it's an admin-only bot)
    if not is_admin(update):
        await query.answer("⛔ Unauthorized.", show_alert=True)
        return
        
    await query.answer()
    
    data = query.data
    if data == "resolved":
        return  # No-op for already clicked buttons
        
    if data.startswith("approve_"):
        app_id = int(data.split("_")[1])
        update_approval_status(app_id, "approved")
        
        from src.approval.queue import get_approval
        app_data = get_approval(app_id)
        execution_result = ""
        if app_data:
            try:
                from src.mcp.client import get_mcp_client
                client = get_mcp_client()
                logger.info("Executing approved action '%s'", app_data['action_type'])
                result = await client.call_tool(app_data['action_type'], app_data['preview_data'])
                
                # Check if result is a dict to extract message
                if isinstance(result, dict) and "message" in result:
                    execution_result = f"\n*Result:* {result['message']}"
                elif isinstance(result, dict) and "error" in result:
                    execution_result = f"\n*Result:* Error - {result['error']}"
                    update_approval_status(app_id, "failed")
                else:
                    execution_result = "\n*Result:* Execution triggered successfully."
            except Exception as e:
                logger.error("Failed to execute approved action: %s", e)
                execution_result = f"\n*Result:* Failed to execute - {str(e)}"
                update_approval_status(app_id, "failed")
        
        # Update message
        original_text = query.message.text or f"Approval #{app_id}"
        await query.edit_message_text(
            text=f"{original_text}\n\nStatus: APPROVED{execution_result}",
            parse_mode=None,
            reply_markup=get_resolved_keyboard("approved")
        )
        
    elif data.startswith("reject_"):
        app_id = int(data.split("_")[1])
        update_approval_status(app_id, "rejected")
        original_text = query.message.text or f"Approval #{app_id}"
        await query.edit_message_text(
            text=f"{original_text}\n\nStatus: REJECTED",
            parse_mode=None,
            reply_markup=get_resolved_keyboard("rejected")
        )


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Main LLM-powered message handler using shared MessageProcessor."""
    if not await admin_guard(update, context):
        return

    # Show typing indicator early
    await update.message.chat.send_action(ChatAction.TYPING)

    content: str | list = ""
    user_text = update.message.text or update.message.caption or ""
    
    # ── Check for Media (Images / PDFs) ──
    try:
        if update.message.photo:
            # Get largest photo
            photo = update.message.photo[-1]
            file = await context.bot.get_file(photo.file_id)
            file_bytes = await file.download_as_bytearray()
            
            import base64
            b64_img = base64.b64encode(file_bytes).decode('utf-8')
            
            content = [
                {"type": "text", "text": user_text if user_text else "What is in this image?"},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}}
            ]
            logger.info("Intercepted image (%d bytes)", len(file_bytes))
            
        elif update.message.document:
            doc = update.message.document
            if doc.mime_type == "application/pdf":
                file = await context.bot.get_file(doc.file_id)
                file_bytes = await file.download_as_bytearray()
                
                logger.info("Intercepted PDF (%d bytes). Extracting text...", len(file_bytes))
                import pymupdf
                with pymupdf.open(stream=file_bytes, filetype="pdf") as pdf:
                    pdf_text = chr(10).join([page.get_text() for page in pdf])
                    
                full_text = f"{user_text}\n\n[PDF Contents]:\n{pdf_text[:30000]}" # cap at 30k chars
                content = full_text.strip()
            # If we want to support other docs later, we'd add them here
            else:
                content = user_text
        else:
            content = user_text
            
    except Exception as exc:
        logger.error("Error processing media attachment: %s", exc)
        await update.message.reply_text("⚠️ Failed to read attachment. Please try again.")
        return

    if not content:
        return

    session_id = _get_session_id(context)
    logger.info("Message from session %s", session_id[:8])

    # ── Task Execution (Delegated to Shared Logic) ──
    active_skill = context.user_data.get("active_skill")
    output = await processor.process_message(session_id, content, active_skill=active_skill)

    # ── Presentation Layer (Telegram-Specific) ──
    renderer = TelegramRenderer(user_transparency_tier=TransparencyTier.STANDARD)
    msg = renderer.render(output)
    
    from telegram.error import BadRequest
    try:
        sent_msg = await update.message.reply_text(
            msg.text, 
            reply_markup=msg.keyboard, 
            parse_mode=msg.parse_mode
        )
    except BadRequest as e:
        if "parse entities" in str(e).lower():
            logger.warning("Failed to parse MarkdownV2. Falling back to escaped text. Error: %s", e)
            output.content.primary.markdown_enabled = False
            for block in output.content.supplementary:
                block.markdown_enabled = False
            msg_fallback = renderer.render(output)
            sent_msg = await update.message.reply_text(
                msg_fallback.text, 
                reply_markup=msg_fallback.keyboard, 
                parse_mode=msg_fallback.parse_mode
            )
        else:
            raise

    # Store to history and output repository
    repo = OutputRepository()
    repo.save(output, platform="telegram", platform_msg_id=sent_msg.message_id)

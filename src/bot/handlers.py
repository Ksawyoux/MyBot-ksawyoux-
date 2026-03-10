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
from src.bot.keyboards import get_approval_keyboard, get_resolved_keyboard

# Phase 7 scheduler imports
from src.scheduler.engine import get_scheduler
from src.scheduler.jobs import run_scheduled_agent_task

# Output formatting imports
from src.output.builder import OutputBuilder
from src.output.rendering.telegram_renderer import TelegramRenderer
from src.output.storage.repository import OutputRepository
from src.output.templates.responses.simple_answer import SimpleAnswerTemplate
from src.output.templates.responses.structured_result import StructuredResultTemplate
from src.output.templates.errors.error import ErrorTemplate
from src.output.core.types import TransparencyTier
from src.output.core.actions import Action, ActionHandler, ActionType
from src.output.core.envelope import TransparencyConfig

logger = get_logger(__name__)

SYSTEM_PROMPT = (
    "You are a personal AI assistant with access to email, calendar, and web search tools. "
    "You are helpful, concise, and proactive.\n\n"
    "## Output Formatting Rules (MANDATORY):\n"
    "1. Use **bold headers** (e.g., *Header*) for distinct sections. NEVER use markdown headers like '# Header'.\n"
    "2. Use bullet points with relevant emojis (e.g., 📧 for email, 📅 for calendar) for lists.\n"
    "3. Keep responses structured and visually professional.\n"
    "4. Use Telegram-compatible Legacy Markdown (use the '*' character for bold, '_' for italics).\n"
    "5. Use a friendly and professional tone.\n\n"
    "When asked to perform an action that requires tools (sending email, creating events, searching the web), "
    "acknowledge the request and explain what you will do."
)


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
        "/memory — Memory stats\n"
        "/memory forget <id> — Remove a fact\n"
        "/schedule list — Show scheduled jobs\n"
        "/schedule add — Create a scheduled job\n"
        "/schedule pause <id> — Pause a job\n"
        "/schedule resume <id> — Resume a job\n"
        "/schedule delete <id> — Delete a job\n"
        "/cancel — Cancel current operation\n\n"
        "Or just *send any message* and I'll answer it!"
    )
    output = OutputBuilder().content_text(text).build()
    msg = TelegramRenderer(user_transparency_tier=TransparencyTier.SILENT).render(output)
    await update.message.reply_text(msg.text, parse_mode=msg.parse_mode)


async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await admin_guard(update, context):
        return
    cache_stats = get_cache_stats()
    conv_stats = get_conversation_stats()
    task_stats = get_task_stats()

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
        f"  Tokens saved: {cache_stats.get('tokens_saved', 0):,}\n"
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


async def pending_approvals_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show list of all pending approvals."""
    if not await admin_guard(update, context):
        return
        
    approvals = get_pending_approvals()
    if not approvals:
        await update.message.reply_text("✅ No pending approvals.")
        return
        
    for app in approvals:
        text = (
            f"🔒 *Approval #{app['id']}*\n"
            f"Action: `{app['action_type']}`\n"
            f"Desc: {app['description']}\n"
            f"Expires: {app['expires_at']}"
        )
        msg = await update.message.reply_text(
            text, 
            parse_mode="Markdown", 
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
                else:
                    execution_result = "\n*Result:* Execution triggered successfully."
            except Exception as e:
                logger.error("Failed to execute approved action: %s", e)
                execution_result = f"\n*Result:* Failed to execute - {str(e)}"
        
        # Update message
        original_text = query.message.text or f"Approval #{app_id}"
        await query.edit_message_text(
            text=f"{original_text}\n\n*Status:* ✅ Approved{execution_result}",
            parse_mode="Markdown",
            reply_markup=get_resolved_keyboard("approved")
        )
        
    elif data.startswith("reject_"):
        app_id = int(data.split("_")[1])
        update_approval_status(app_id, "rejected")
        original_text = query.message.text or f"Approval #{app_id}"
        await query.edit_message_text(
            text=f"{original_text}\n\n*Status:* ❌ Rejected",
            parse_mode="Markdown",
            reply_markup=get_resolved_keyboard("rejected")
        )


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Main LLM-powered message handler."""
    if not await admin_guard(update, context):
        return

    user_text = update.message.text or ""
    if not user_text.strip():
        return

    session_id = _get_session_id(context)
    logger.info("Message from session %s: %.80s", session_id[:8], user_text)

    # Show typing indicator
    await update.message.chat.send_action(ChatAction.TYPING)

    # Save user message
    save_message(session_id, "user", user_text)

    # ── Phase 2: Memory Context & Summarization ──
    # Get conversation history for context, triggering summarization if needed
    history, needs_summarization = get_short_term_context(session_id, limit=20)
    
    # Remove the message we just added (last item) from history to avoid duplication
    context_history = history[:-1] if history else []

    if needs_summarization:
        # Background task
        import asyncio
        asyncio.create_task(summarize_session(session_id, context_history))
        # Keep only the last 5 messages for this immediate prompt
        context_history = context_history[-5:]

    # Enrich prompt with Long-Term Memory (vector search)
    enriched_prompt = await enrich_prompt_with_context(user_text)

    # ── Phase 3: Intent Classification ──
    # Classify the prompt into simple, complex, or scheduled
    classification = await classify_task(user_text)
    task_type = classification["type"]
    priority = classification["priority"]
    logger.info("Message classified as %s (priority %d)", task_type, priority)

    # ── Task Execution ──
    task_id = create_task(task_type, {"session_id": session_id, "prompt": user_text[:500]}, priority=priority)
    update_task(task_id, status="in_progress")

    try:
        if task_type == "simple":
            # Direct LLM call
            result = await complete(
                prompt=enriched_prompt,
                model_tier="lightweight",
                system_prompt=SYSTEM_PROMPT,
                conversation_history=context_history,
                priority=0, # Priority Interactive
            )
            response_text = result["response"]
            model_used = result["model"]
            tokens_used = result["tokens"]
            
            # Phase 1: Use new simple answer output template
            output = SimpleAnswerTemplate(text=response_text, task_id=str(task_id)).render()
            output.metadata = {"model": model_used}
            
        elif task_type == "complex":
            try:
                # Phase 6: Execute via CrewAI
                from src.agents.crew_manager import execute_crew_task
                crew_result = await execute_crew_task(classification["intent"], enriched_prompt, task_id)
                response_text = crew_result
                model_used = "crewai-pipeline"
                tokens_used = 0 
                
                output = StructuredResultTemplate(data=response_text, task_id=str(task_id)).render()
                output.metadata = {"model": model_used}
                
            except (ImportError, ModuleNotFoundError):
                logger.warning("CrewAI not installed. Falling back to capable LLM for complex task.")
                result = await complete(
                    prompt=enriched_prompt,
                    model_tier="capable",
                    system_prompt=SYSTEM_PROMPT,
                    conversation_history=context_history,
                    priority=0,
                )
                response_text = result["response"]
                model_used = result["model"]
                tokens_used = result["tokens"]
                output = SimpleAnswerTemplate(text=response_text, task_id=str(task_id)).render()

            
        elif task_type == "scheduled":
            # Phase 7: Send to Scheduler
            
            # Use LLM to extract cron expression
            extract_prompt = f"Convert this request into a cron expression and a clean prompt string.\nRequest: {user_text}\nOutput FORMAT EXACTLY like this:\nCRON: * * * * *\nPROMPT: task description"
            
            result = await complete(
                prompt=extract_prompt,
                model_tier="lightweight",
                system_prompt="You are a strict cron job parser. Reply ONLY with the requested format.",
            )
            
            lines = result["response"].strip().split('\n')
            cron_expr = None
            task_prompt = user_text
            
            for line in lines:
                if line.startswith("CRON:"):
                    cron_expr = line.replace("CRON:", "").strip()
                elif line.startswith("PROMPT:"):
                    task_prompt = line.replace("PROMPT:", "").strip()
            
            if not cron_expr:
                response_text = "❌ Could not understand the schedule format. Please try rephrasing (e.g., 'every day at 9am')."
                output = ErrorTemplate(title="Invalid Schedule", description="Could not understand the schedule format. Please try rephrasing (e.g., 'every day at 9am').", task_id=str(task_id)).render()
            else:
                from apscheduler.triggers.cron import CronTrigger
                try:
                    trigger = CronTrigger.from_crontab(cron_expr)
                    scheduler = get_scheduler()
                    job = scheduler.add_job(
                        run_scheduled_agent_task,
                        trigger=trigger,
                        args=[session_id, task_prompt],
                        name=f"User Task: {task_prompt[:30]}"
                    )
                    response_text = f"⏰ *Job Scheduled*\nID: `{job.id}`\nSchedule: `{cron_expr}`\nTask: {task_prompt}"
                    output = SimpleAnswerTemplate(text=response_text, task_id=str(task_id)).render()
                except ValueError as ve:
                    response_text = f"❌ Invalid cron format extracted: `{cron_expr}`"
                    output = ErrorTemplate(title="Invalid Schedule", description=f"Invalid cron format extracted: `{cron_expr}`", task_id=str(task_id)).render()
            
            model_used = result["model"]
            tokens_used = result["tokens"]
            
        else:
            raise ValueError(f"Unknown task type: {task_type}")

        # Save assistant response
        save_message(session_id, "assistant", response_text, tokens=tokens_used)
        
        # ── Phase 2: Background Fact Extraction ──
        import asyncio
        extraction_context = context_history[-4:] + [{"role": "user", "content": user_text}, {"role": "assistant", "content": response_text}]
        asyncio.create_task(extract_and_store_facts(session_id, extraction_context))

        update_task(
            task_id,
            status="completed",
            model_used=model_used,
            tokens_used=tokens_used,
            output_data=output.model_dump(mode='json'),
        )

        # Store to output history
        renderer = TelegramRenderer(user_transparency_tier=TransparencyTier.STANDARD)
        msg = renderer.render(output)
        
        from telegram.error import BadRequest
        try:
            sent_msg = await update.message.reply_text(msg.text, reply_markup=msg.keyboard, parse_mode=msg.parse_mode)
        except BadRequest as e:
            if "parse entities" in str(e).lower():
                logger.warning("Failed to parse MarkdownV2. Falling back to escaped text. Error: %s", e)
                output.content.primary.markdown_enabled = False
                for block in output.content.supplementary:
                    block.markdown_enabled = False
                msg_fallback = renderer.render(output)
                sent_msg = await update.message.reply_text(msg_fallback.text, reply_markup=msg_fallback.keyboard, parse_mode=msg_fallback.parse_mode)
            else:
                raise

        repo = OutputRepository()
        repo.save(output, platform="telegram", platform_msg_id=sent_msg.message_id)

    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code
        logger.error("LLM API returned HTTP %s: %s", status_code, exc)
        update_task(task_id, status="failed", error_message=f"HTTP {status_code}")
        
        if status_code == 429:
            err_msg = "⏳ I'm receiving too many requests right now. Please try again in a minute."
        elif status_code >= 500:
            err_msg = "🔌 The AI provider is currently experiencing downtime. Please try again later."
        else:
            err_msg = f"⚠️ The AI provider returned an error (HTTP {status_code})."
            
        output = ErrorTemplate(title="API Error", description=err_msg, task_id=str(task_id)).render()
        msg = TelegramRenderer().render(output)
        await update.message.reply_text(msg.text, reply_markup=msg.keyboard, parse_mode=msg.parse_mode)
        
    except httpx.RequestError as exc:
        logger.error("Network error reaching LLM API: %s", exc)
        update_task(task_id, status="failed", error_message="Network Error")
        output = ErrorTemplate(title="Network Error", description="Could not reach the AI provider. Please check my connection.", task_id=str(task_id)).render()
        msg = TelegramRenderer().render(output)
        await update.message.reply_text(msg.text, reply_markup=msg.keyboard, parse_mode=msg.parse_mode)

    except Exception as exc:
        logger.error("Unexpected error in message_handler: %s", exc, exc_info=True)
        update_task(task_id, status="failed", error_message=str(exc))
        output = ErrorTemplate(title="Unexpected Error", description="Sorry, I ran into an unexpected error processing your request.", task_id=str(task_id)).render()
        msg = TelegramRenderer().render(output)
        await update.message.reply_text(msg.text, reply_markup=msg.keyboard, parse_mode=msg.parse_mode)

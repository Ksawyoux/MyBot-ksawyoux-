"""
src/shared/message_processor.py — Core message processing logic decoupled from platform-specific handlers.
"""

import asyncio
import httpx
from typing import Optional, Dict, Any, List

from src.utils.logging import get_logger
from src.llm.gateway import complete
from src.db.conversations import save_message
from src.db.tasks import create_task, update_task
from src.memory.short_term import get_short_term_context
from src.memory.summarizer import summarize_session
from src.memory.fact_extractor import extract_and_store_facts
from src.router.context_enricher import enrich_prompt_with_context
from src.router.task_classifier import classify_task
from src.output.core.envelope import OutputEnvelope
from src.output.templates.responses.simple_answer import SimpleAnswerTemplate
from src.output.templates.responses.structured_result import StructuredResultTemplate
from src.output.templates.errors.error import ErrorTemplate
from src.scheduler.engine import get_scheduler
from src.scheduler.jobs import run_scheduled_agent_task

logger = get_logger(__name__)

class MessageProcessor:
    def __init__(self, system_prompt: str):
        self.system_prompt = system_prompt

    async def process_message(self, session_id: str, user_text: str) -> OutputEnvelope:
        """
        Main entry point for processing a user message.
        Handles memory, intent, task execution and database updates.
        Returns an OutputEnvelope that can be rendered by the caller.
        """
        # 1. Save user message
        save_message(session_id, "user", user_text)

        # 2. Memory Context & Summarization
        history, needs_summarization = get_short_term_context(session_id, limit=20)
        # Remove the message we just added (last item) from history to avoid duplication
        context_history = history[:-1] if history else []

        if needs_summarization:
            # Background task
            asyncio.create_task(summarize_session(session_id, context_history))
            # Keep only the last 5 messages for this immediate prompt
            context_history = context_history[-5:]

        # 3. Enrich prompt with Long-Term Memory (vector search)
        enriched_prompt = await enrich_prompt_with_context(user_text)

        # 4. Intent Classification
        classification = await classify_task(user_text)
        task_type = classification["type"]
        priority = classification["priority"]
        logger.info("Message classified as %s (priority %d)", task_type, priority)

        # 5. Task Creation
        task_id = create_task(task_type, {"session_id": session_id, "prompt": user_text[:500]}, priority=priority)
        update_task(task_id, status="in_progress")

        try:
            output = None
            response_text = ""
            model_used = ""
            tokens_used = 0

            if task_type == "simple":
                # Direct LLM call
                result = await complete(
                    prompt=enriched_prompt,
                    model_tier="lightweight",
                    system_prompt=self.system_prompt,
                    conversation_history=context_history,
                    priority=0,
                )
                response_text = result["response"]
                model_used = result["model"]
                tokens_used = result["tokens"]
                
                output = SimpleAnswerTemplate(text=response_text, task_id=str(task_id)).render()
                output.metadata = {"model": model_used}

            elif task_type == "complex":
                try:
                    # Execute via CrewAI
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
                        system_prompt=self.system_prompt,
                        conversation_history=context_history,
                        priority=0,
                    )
                    response_text = result["response"]
                    model_used = result["model"]
                    tokens_used = result["tokens"]
                    output = SimpleAnswerTemplate(text=response_text, task_id=str(task_id)).render()
                    output.metadata = {"model": model_used}

            elif task_type == "scheduled":
                # Phase 7: Send to Scheduler
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
                    response_text = "❌ Could not understand the schedule format."
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
                        response_text = f"⏰ Job Scheduled\nID: {job.id}\nSchedule: {cron_expr}\nTask: {task_prompt}"
                        output = SimpleAnswerTemplate(text=response_text, task_id=str(task_id)).render()
                    except ValueError:
                        response_text = f"❌ Invalid cron format extracted: {cron_expr}"
                        output = ErrorTemplate(title="Invalid Schedule", description=f"Invalid cron format extracted: {cron_expr}", task_id=str(task_id)).render()
                
                model_used = result["model"]
                tokens_used = result.get("tokens", 0)

            # Finalize
            if output:
                # Save assistant response
                if response_text:
                    save_message(session_id, "assistant", response_text, tokens=tokens_used)
                    # Fact extraction in background
                    extraction_context = context_history[-4:] + [{"role": "user", "content": user_text}, {"role": "assistant", "content": response_text}]
                    asyncio.create_task(extract_and_store_facts(session_id, extraction_context))

                update_task(
                    task_id,
                    status="completed",
                    model_used=model_used,
                    tokens_used=tokens_used,
                    output_data=output.model_dump(mode='json'),
                )
                return output

            raise ValueError(f"Unknown task type or failure: {task_type}")

        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            logger.error("LLM API returned HTTP %s: %s", status_code, exc)
            update_task(task_id, status="failed", error_message=f"HTTP {status_code}")
            
            err_msg = f"⚠️ The AI provider returned an error (HTTP {status_code})."
            if status_code == 429:
                err_msg = "⏳ I'm receiving too many requests right now. Please try again in a minute."
            elif status_code >= 500:
                err_msg = "🔌 The AI provider is currently experiencing downtime. Please try again later."
                
            return ErrorTemplate(title="API Error", description=err_msg, task_id=str(task_id)).render()
            
        except httpx.RequestError as exc:
            logger.error("Network error reaching LLM API: %s", exc)
            update_task(task_id, status="failed", error_message="Network Error")
            return ErrorTemplate(title="Network Error", description="Could not reach the AI provider. Please check my connection.", task_id=str(task_id)).render()

        except Exception as exc:
            logger.error("Unexpected error in MessageProcessor: %s", exc, exc_info=True)
            update_task(task_id, status="failed", error_message=str(exc))
            return ErrorTemplate(title="Unexpected Error", description="Sorry, I ran into an unexpected error processing your request.", task_id=str(task_id)).render()

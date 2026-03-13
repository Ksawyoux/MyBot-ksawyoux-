"""
src/shared/message_processor.py — Core message processing logic decoupled from platform-specific handlers.
"""

import asyncio
import os
import httpx
from typing import Optional, Dict, Any, List

from src.utils.logging import get_logger
from src.llm.gateway import complete
from src.db.connection import get_db
from src.db.models import Fact
from src.mcp.client import get_mcp_client
from src.config.prompts import build_system_prompt
from src.db.conversations import save_message
from src.db.tasks import create_task, update_task
from src.memory.short_term import get_short_term_context
from src.memory.summarizer import summarize_session
from src.memory.fact_extractor import extract_and_store_facts
from src.router.context_enricher import enrich_prompt_with_context
from src.router.task_classifier import classify_task
from src.router.router import route_message # Keep for now as part of the flow or refactor out
from src.config.routing import route_by_action
from src.handlers.core import register_core_handlers
from src.output.core.envelope import OutputEnvelope
from src.output.templates.responses.simple_answer import SimpleAnswerTemplate
from src.output.templates.responses.structured_result import StructuredResultTemplate
from src.output.templates.errors.error import ErrorTemplate
from src.scheduler.engine import get_scheduler
from src.scheduler.jobs import run_scheduled_agent_task

logger = get_logger(__name__)

class MessageProcessor:
    def __init__(self):
        # Initialize the routing system
        register_core_handlers()

    def _get_skill_prompt(self, active_skill: Optional[str]) -> str:
        """Returns the content of the active skill's SKILL.md file if one is active."""
        if not active_skill:
            return ""
            
        try:
            skill_file_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "skills",
                active_skill,
                "SKILL.md"
            )
            if os.path.exists(skill_file_path):
                with open(skill_file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                return f"\n\n--- ACTIVE SKILL: {active_skill} ---\n{content}\n--------------------------------\n"
        except Exception as e:
            logger.error("Failed to read skill %s: %s", active_skill, e)
            
        return ""

    async def process_message(self, session_id: str, content: str | list, active_skill: Optional[str] = None) -> OutputEnvelope:
        """
        Main entry point for processing a user message.
        Handles memory, intent, task execution and database updates.
        Returns an OutputEnvelope that can be rendered by the caller.
        """
        # 0. Fetch Fresh Context for System Prompt
        with get_db() as db:
            facts = db.query(Fact).filter(Fact.superseded_by == None).all()
            user_facts = [{"key": f.key, "value": f.value} for f in facts]

        client = get_mcp_client()
        servers = client.get_connected_servers()
        
        # Determine tier (initial guess is agentic, refined after classification)
        system_prompt = build_system_prompt(
            user_facts=user_facts,
            connected_servers=servers,
            tier="agentic"
        )
        
        # Merge skill prompt if provided
        effective_system_prompt = system_prompt + self._get_skill_prompt(active_skill)
        
        # Determine raw text representation for databases and classification
        if isinstance(content, list):
            user_text = " ".join([item.get("text", "") for item in content if item.get("type") == "text"]).strip()
            if not user_text:
                user_text = "[Media Attachment]"
        else:
            user_text = content
            
        # 1. Save user message
        save_message(session_id, "user", user_text)

        # 2. Memory Context & Summarization
        history, needs_summarization = get_short_term_context(session_id, limit=30)
        # Remove the message we just added (last item) from history to avoid duplication
        context_history = history[:-1] if history else []

        if needs_summarization:
            # Background task
            asyncio.create_task(summarize_session(session_id, context_history))
            # Keep only the last 5 messages for this immediate prompt
            context_history = context_history[-5:]

        # 3. Enrich text prompt with Long-Term Memory (vector search)
        enriched_text_prompt = await enrich_prompt_with_context(user_text)
        
        # Combine if multimodal
        if isinstance(content, list):
            # Find the text part and replace it, or append if missing
            enriched_content = []
            text_injected = False
            for item in content:
                if item.get("type") == "text":
                    enriched_content.append({"type": "text", "text": enriched_text_prompt})
                    text_injected = True
                else:
                    enriched_content.append(item)
            if not text_injected:
                enriched_content.append({"type": "text", "text": enriched_text_prompt})
        else:
            enriched_content = enriched_text_prompt

        # 4. Intent Classification
        classification = await classify_task(user_text)
        task_type = classification["type"]
        priority = classification["priority"]
        
        # If media is present, route to simple LLM but use vision tier
        if isinstance(content, list) and task_type != "simple":
            logger.info("Media attachment detected. Coercing to lightweight vision task.")
            task_type = "simple"
            
        logger.info("Message classified as %s (priority %d)", task_type, priority)

        # 5. Task Creation
        task_id = create_task(task_type, {"session_id": session_id, "prompt": user_text[:500]}, priority=priority)
        update_task(task_id, status="in_progress")

        # 6. Hybrid Routing (Internal vs External)
        internal_response = await route_message(user_text, classification["intent"], {"session_id": session_id})
        if internal_response:
            logger.info("Request handled by internal router.")
            save_message(session_id, "assistant", internal_response)
            output = SimpleAnswerTemplate(text=internal_response, task_id=str(task_id)).render()
            update_task(task_id, status="completed", model_used="internal-router", output_data=output.model_dump(mode='json'))
            return output

        # Prepare metadata for prefix caching and handlers
        message_tier = classification["intent"].get("tier", "agentic")
        metadata = {
            "user_facts": user_facts,
            "servers": servers,
            "tier": message_tier,
            "active_task": None # Add task context if available in future phases
        }

        # 7. Explicit Routing Execution
        try:
            # Prepare context for handlers
            handler_context = {
                "session_id": session_id,
                "task_id": task_id,
                "user_facts": user_facts,
                "servers": servers,
                "system_prompt": effective_system_prompt,
                "history": context_history,
                "metadata": metadata,
                "enriched_content": enriched_content
            }

            # Execute via routing config
            response_text = await route_by_action(classification["intent"], user_text, handler_context)
            
            # ── NEVER SEND EMPTY ──────────────────────────────────
            if not response_text or (isinstance(response_text, str) and not response_text.strip()):
                logger.warning(f"Empty response generated for: {user_text}")
                response_text = (
                    "I wasn't able to process that request. "
                    "Can you try rephrasing?"
                )

            # If the handler didn't return an OutputEnvelope, wrap it
            if isinstance(response_text, str):
                output = SimpleAnswerTemplate(text=response_text, task_id=str(task_id)).render()
                model_used = "routed-handler" # Could be refined by handlers
            else:
                # Assume it's already an OutputEnvelope or similar
                output = response_text
                response_text = getattr(output, 'text', str(output)) # Simplification
            
            # Tokens are currently tracked within handlers if needed, 
            # defaulting to 0 here for simplicity in this refactor step.
            tokens_used = 0 
            model_used = "routed-handler"

            # Finalize
            if not output:
                 logger.warning("No output generated by handler for action %s. Falling back to agentic_respond.", classification["intent"].get("action"))
                 from src.handlers.core import agentic_respond
                 response_text = await agentic_respond(user_text, handler_context)
                 output = SimpleAnswerTemplate(text=response_text, task_id=str(task_id)).render()

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


import asyncio
import os
from src.router.task_classifier import classify_task
from src.config.routing import route_by_action
from src.handlers.core import register_core_handlers
from src.utils.logging import get_logger

# Ensure logs are visible
import logging
logging.basicConfig(level=logging.INFO)

async def test():
    from src.llm.request_queue import get_request_queue
    get_request_queue().start(asyncio.get_running_loop())
    register_core_handlers()
    
    prompt = "Access this website youness-aboukad.vercel.app"
    print(f"\n--- Testing Prompt: {prompt} ---")
    
    classification = await classify_task(prompt)
    print(f"Classification: {classification}")
    
    intent = classification["intent"]
    context = {
        "session_id": "test_session",
        "task_id": 999,
        "history": [],
        "system_prompt": "You are a helpful assistant.",
        "metadata": {"tier": intent.get("tier", "agentic")}
    }
    
    print("\n--- Routing ---")
    try:
        response = await route_by_action(intent, prompt, context)
        print(f"Response: {response}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test())

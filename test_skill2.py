import asyncio
from src.router.intent_parser import parse_intent
from src.agents.skill_loader import create_skill_agent
from src.agents.crew_manager import _get_crewai_llm
from src.llm.request_queue import get_request_queue

async def main():
    queue = get_request_queue()
    queue.start()
    
    try:
        print("Testing Intent Parsing...")
        intent = await parse_intent("Use the seo-audit skill to analyze my site structure.")
        print(f"Parsed Intent: {intent}")

        if intent["action"] == "skill":
            print("\nTesting skill agent loading...")
            llm = _get_crewai_llm("lightweight")
            agent = create_skill_agent(intent["skill_name"], llm)
            print(f"Agent Role: {agent.role}")
            print(f"Agent Goal: {agent.goal[:100]}...")
            print(f"Backstory Length: {len(agent.backstory)} chars")
    finally:
        queue.stop()

if __name__ == "__main__":
    asyncio.run(main())

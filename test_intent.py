import asyncio
from src.router.intent_parser import parse_intent
from src.llm.request_queue import get_request_queue

async def main():
    get_request_queue().start()
    
    print("Testing 'Who are you?'")
    result1 = await parse_intent("Who are you?")
    print(f"Result: {result1}")
    
    print("\nTesting 'What can you do?'")
    result2 = await parse_intent("What can you do?")
    print(f"Result: {result2}")

if __name__ == "__main__":
    asyncio.run(main())

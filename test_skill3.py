import asyncio
from src.router.intent_parser import parse_intent
from src.llm.request_queue import get_request_queue

async def main():
    queue = get_request_queue()
    queue.start()
    try:
        print(await parse_intent("Use the seo-audit skill to analyze my site structure."))
        print(await parse_intent("I want you to use the 'ai-seo' skill to write a blog post."))
    finally:
        queue.stop()

if __name__ == "__main__":
    asyncio.run(main())

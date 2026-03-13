import re
import logging
from typing import Optional, Dict, Any
from src.tools.web_search import search_tool, format_results_for_context
from src.tools.web_fetch import fetch_url
from src.tools.web_cache import web_cache

logger = logging.getLogger(__name__)

async def handle_search(user_msg: str, context: dict) -> Optional[str]:
    """Handles search intent: News, Instant, or General."""
    msg_lower = user_msg.lower()
    
    # 1. Determine search type
    search_type = "general"
    if any(kw in msg_lower for kw in ["news", "latest", "recent", "today", "just happened"]):
        search_type = "news"
    elif any(msg_lower.startswith(kw) for kw in ["what is", "who is", "define", "meaning of"]):
        search_type = "instant"

    # 2. Check Cache
    cached = web_cache.get(search_type, user_msg)
    if cached:
        logger.info(f"Search cache hit for {search_type}: {user_msg}")
        return cached

    # 3. Perform Search
    results = []
    if search_type == "instant":
        ans = await search_tool.instant_answer(user_msg)
        if ans:
            # Format instant answer
            formatted = f"Found an instant answer:\n{ans.get('body', '')}\nSource: {ans.get('href', 'DuckDuckGo')}"
            web_cache.set("instant", user_msg, formatted, 3600)
            return formatted
        # Fallback to general if no instant answer
        results = await search_tool.web_search(user_msg)
    elif search_type == "news":
        results = await search_tool.news_search(user_msg)
        ttl = 300 # 5 mins
    else:
        results = await search_tool.web_search(user_msg)
        ttl = 600 # 10 mins

    if not results:
        return f"I couldn't find any results for '{user_msg}'."

    # 4. Format for Context and Cache
    # We return None if we want the LLM to synthesize, 
    # but the instructions say "handle_search() flow: Got results? Yes -> Format as context -> Feed to LLM"
    # Wait, the router returns a string if handled internally, or None to proceed to CrewAI.
    # If we want a summary, we should probably return the raw results or formatted context to the caller
    # but the router.py:route_message expects a final string or None.
    # If we return a string here, it BYPASSES the LLM synthesis.
    # However, Phase 2.2 says: "Synthesize answer" in flow.
    # This implies router handles the tool call, then we still might want LLM to polish it.
    
    # Let's follow the instruction: "Return string if handled internally, or None to proceed to LLM."
    # If we return None, the CrewAI pipeline will see the intent 'search' and should handle it.
    # BUT Phase 2.2 specifically asks for handle_search() and handle_url_fetch() in the ROUTER.
    
    # I'll implement them to return a rich context string that the MessageProcessor can then use,
    # or just return None and let the Agentic pipeline handle it?
    # Actually, the internal data tier returns a string to avoid LLM.
    # For search, we WANT LLM synthesis. So handle_search should probably return None 
    # and just enrich the context if possible, or we let the Agent handles it.
    
    # Wait, Phase 2.2 ACTION MAP: "search" -> handle_search(). 
    # This map is in the ROUTER section.
    # If I return a string from router, it is the FINAL answer.
    # If I want LLM synthesis, I should return None.
    
    # I'll return None for now so the CrewAI pipeline handles the tool use and synthesis,
    # OR I implement the synthesis here by calling the LLM directly (mini model).
    # Given Phase 2.2 flow "Synthesize answer", and Phase 3 is "LLM Integration",
    # I'll let the router return None for action 'search' and 'web_browse' 
    # AFTER ensuring the tools are available to the LLM.
    
    return None

async def handle_url_fetch(user_msg: str, context: dict) -> Optional[str]:
    """Handles URL fetch intent."""
    url_match = re.search(r'https?://\S+', user_msg)
    if not url_match:
        return None # Let it fall back to search
    
    url = url_match.group(0)
    
    # Check cache
    cached = web_cache.get("url", url)
    if cached:
        return None # Let LLM synthesize from cached content
    
    return None

async def handle_web_browse(user_msg: str, context: dict) -> str:
    """Handle web browsing requests."""
    from src.llm.gateway import complete
    from src.config.prompts import build_system_prompt
    
    # 1. Extract URL
    url = extract_url(user_msg, context)
    
    if not url:
        return "I couldn't find a URL in your message. Can you share the link?"
    
    # Ensure https://
    if not url.startswith("http"):
        url = f"https://{url}"
    
    logger.info(f"🌐 Browsing: {url}")
    
    try:
        # 2. Use web_fetch to get page content
        page = await fetch_url(url)
        
        if page.get("status") == "error":
            return f"⚠️ Couldn't access *{url}*: {page.get('reason', 'Unknown error')}"
        
        if not page.get("content"):
            return f"⚠️ Page loaded but had no readable content."
        
        # 3. Feed content to LLM for analysis
        # Extract facts and servers from context if available
        user_facts = context.get("user_facts", [])
        servers = context.get("servers", [])
        
        system_prompt = build_system_prompt(
            user_facts=user_facts,
            connected_servers=servers,
            tier="agentic",
        )
        
        analysis_prompt = (
            f"The user asked: {user_msg}\n\n"
            f"Here is the content from *{page.get('title', 'No Title')}* ({page.get('url')}):\n\n"
            f"{page.get('content', '')[:12000]}\n\n" # Truncate to avoid context overflow
            f"Analyze this page and respond to the user's request."
        )
        
        result = await complete(
            prompt=analysis_prompt,
            model_tier="capable", # Use gpt-4o or similar
            system_prompt=system_prompt,
        )
        
        return result["response"]
        
    except Exception as e:
        logger.error(f"Error browsing {url}: {e}")
        return f"⚠️ Error browsing *{url}*: {str(e)}"


def extract_url(text: str, context: Optional[dict] = None) -> str | None:
    """Extract URL from user message or recent history."""
    # 1. Direct URL in text
    match = re.search(r'https?://[^\s<>"]+', text)
    if match:
        return match.group(0)
    
    # 2. Domain-style (example.com, something.vercel.app)
    tlds = r'(?:com|org|net|io|app|dev|co|me|ai|vercel\.app|netlify\.app|github\.io)'
    match = re.search(rf'([a-zA-Z0-9-]+\.{tlds}[^\s]*)', text)
    if match:
        return match.group(0)
    
    # 3. Look in history if "blog" or "my" or "access" mentioned
    if context and context.get("history") and any(kw in text.lower() for kw in ["blog", "access", "my", "link", "site"]):
        history = context.get("history", [])
        # Look backwards through history for the last mentioned URL
        for msg in reversed(history):
            content = msg.get("content", "")
            match = re.search(r'https?://[^\s<>"]+', content)
            if match:
                logger.info(f"Retrieved URL from history: {match.group(0)}")
                return match.group(0)
            
            # Also check domain style in history
            match = re.search(rf'([a-zA-Z0-9-]+\.{tlds}[^\s]*)', content)
            if match:
                logger.info(f"Retrieved domain from history: {match.group(0)}")
                return match.group(0)

    return None

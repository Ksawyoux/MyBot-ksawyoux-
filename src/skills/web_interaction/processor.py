"""
src/skills/web_interaction/processor.py — Processes raw HTML into LLM-friendly formats.
"""

import re
from bs4 import BeautifulSoup
from typing import List, Dict, Any
from src.utils.logging import get_logger

logger = get_logger(__name__)

def clean_html(html: str) -> str:
    """
    Cleans HTML by removing script tags, styles, and other noise.
    Returns a simplified text/markdown representation.
    """
    soup = BeautifulSoup(html, "html.parser")
    
    # Remove unwanted elements
    for element in soup(["script", "style", "nav", "footer", "header", "noscript", "svg", "iframe", "form"]):
        element.decompose()

    # Get text
    text = soup.get_text(separator="\n")
    
    # Simple whitespace cleaning
    lines = (line.strip() for line in text.splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    text = "\n".join(chunk for chunk in chunks if chunk)
    
    return text

def extract_interactive_elements(html: str) -> List[Dict[str, str]]:
    """
    Extracts interactive elements like links and buttons for the LLM to 'see'.
    """
    soup = BeautifulSoup(html, "html.parser")
    elements = []
    
    # Extract links
    for idx, a in enumerate(soup.find_all("a", href=True)):
        text = a.get_text(strip=True)
        if text and len(text) > 2:
            elements.append({
                "id": str(idx),
                "type": "link",
                "text": text,
                "href": a["href"]
            })
            
    # Extract buttons
    for idx, btn in enumerate(soup.find_all("button")):
        text = btn.get_text(strip=True)
        if text:
            elements.append({
                "id": f"btn_{idx}",
                "type": "button",
                "text": text
            })
            
    return elements

def get_page_state_representation(html: str, max_tokens: int = 2000) -> str:
    """
    Creates a text representation of the page state for the LLM.
    Includes cleaned text and a list of interactive elements.
    """
    text = clean_html(html)
    elements = extract_interactive_elements(html)
    
    # Format elements
    elements_str = "\n".join([f"[{e['id']}] {e['type'].upper()}: {e['text']}" for e in elements[:50]]) # Limit to 50 elements
    
    representation = f"--- PAGE CONTENT ---\n{text[:max_tokens]}\n\n--- INTERACTIVE ELEMENTS ---\n{elements_str}"
    
    return representation

def chunk_content(text: str, chunk_size: int = 1000) -> List[str]:
    """Chunks text for LLM context window management."""
    return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]

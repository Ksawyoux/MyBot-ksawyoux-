"""
tests/unit/test_router.py — Tests for intent parser logic
"""

import pytest
from src.router.task_classifier import classify_task

@pytest.mark.asyncio
async def test_classify_task_schedule(monkeypatch):
    """Mock the LLM parser to test the routing logic."""
    async def mock_parse(*args, **kwargs):
        return {
            "action": "schedule",
            "urgency": "normal",
            "entities": [],
            "complexity_hint": "simple"
        }
    
    monkeypatch.setattr("src.router.task_classifier.parse_intent", mock_parse)
    
    result = await classify_task("remind me tomorrow")
    assert result["type"] == "scheduled"
    assert result["priority"] == 3

@pytest.mark.asyncio
async def test_classify_task_high_priority(monkeypatch):
    async def mock_parse(*args, **kwargs):
        return {
            "action": "other",
            "urgency": "high",
            "entities": [],
            "complexity_hint": "complex"
        }
    
    monkeypatch.setattr("src.router.task_classifier.parse_intent", mock_parse)
    
    result = await classify_task("URGENT: stop the server")
    assert result["type"] == "complex"
    assert result["priority"] == 0

import pytest
import asyncio
from unittest.mock import patch, MagicMock
from src.router.intent_parser import parse_intent, _fallback_classify, _clean_json_response, _validate_intent

# --- Clean response tests ---
def test_clean_json_response_markdown():
    raw = "```json\n{\n\"tier\": \"fast\"\n}\n```"
    assert _clean_json_response(raw) == '{\n"tier": "fast"\n}'

def test_clean_json_response_trailing_commas():
    raw = '{"tier": "fast", "action": "social",}'
    assert _clean_json_response(raw) == '{"tier": "fast", "action": "social"}'

    raw_array = '{"entities": ["a", "b",]}'
    assert _clean_json_response(raw_array) == '{"entities": ["a", "b"]}'

def test_clean_json_response_pure():
    raw = '{"tier": "fast"}'
    assert _clean_json_response(raw) == '{"tier": "fast"}'

# --- Validation and Fallback logic tests ---
def test_validate_intent_invalid_tier():
    raw = {"tier": "superfast", "action": "social"}
    validated = _validate_intent(raw, "hello bro")
    assert validated["tier"] == "fast"
    
def test_validate_intent_invalid_action():
    raw = {"tier": "agentic", "action": "hack_mainframe"}
    validated = _validate_intent(raw, "hack the mainframe")
    assert validated["action"] == "other"
    
def test_validate_intent_backward_compat():
    raw = {"tier": "agentic"}
    validated = _validate_intent(raw, "research AI")
    assert validated["complexity_hint"] == "complex"
    assert validated["complexity"] == "medium"
    
def test_fallback_social():
    res = _fallback_classify("yooooooo")
    assert res["tier"] == "fast"
    assert res["action"] == "social"
    
def test_fallback_internal():
    res = _fallback_classify("show my scheduled tasks")
    assert res["tier"] == "fast"
    assert res["action"] == "internal_query"

def test_fallback_reminder():
    res = _fallback_classify("remind me to sleep")
    assert res["tier"] == "scheduled"
    assert res["action"] == "reminder"

def test_fallback_email():
    res = _fallback_classify("check my email please")
    assert res["tier"] == "fast"
    assert res["action"] == "other"

def test_fallback_calendar():
    res = _fallback_classify("whats on my calendar today")
    assert res["tier"] == "fast"
    assert res["action"] == "other"

def test_fallback_research():
    res = _fallback_classify("research the top 10 richest people")
    assert res["tier"] == "agentic"
    assert res["action"] == "search"

def test_fallback_search():
    res = _fallback_classify("search for flights to NYC")
    assert res["tier"] == "agentic"
    assert res["action"] == "search"
    
def test_fallback_plan():
    res = _fallback_classify("plan a trip to Paris")
    assert res["tier"] == "fast"
    assert res["action"] == "other"

def test_fallback_other():
    res = _fallback_classify("what is the meaning of life")
    assert res["tier"] == "fast"
    assert res["action"] == "other"

# --- Mocking LLM API Calls for Unit Tests ---
@pytest.mark.asyncio
@patch('src.router.intent_parser.get_dynamic_system_prompt', return_value="dummy_sys_prompt")
@patch('src.llm.gateway.complete')
async def test_parse_intent_success(mock_complete, mock_get_sys):
    mock_complete.return_value = {
        "response": '{"tier": "agentic", "action": "research", "requires_tools": true, "complexity": "high"}'
    }
    
    intent = await parse_intent("research quantum computing")
    assert intent["tier"] == "agentic"
    assert intent["action"] == "search"
    assert intent["requires_tools"] is True
    assert intent["complexity"] == "low"
    assert intent["complexity_hint"] == "complex"

@pytest.mark.asyncio
@patch('src.router.intent_parser.get_dynamic_system_prompt', return_value="dummy_sys_prompt")
@patch('src.llm.gateway.complete')
async def test_parse_intent_llm_fails_triggering_fallback(mock_complete, mock_get_sys):
    # Simulate LLM returning hot garbage or failing
    mock_complete.return_value = {
        "response": '```json\\nthis is not valid json\\n```'
    }
    
    # Even if LLM fails, we expect the fallback rule to match "other" for short msg
    intent = await parse_intent("check my email right now")
    assert intent["tier"] == "fast"
    assert intent["action"] == "other"
    assert intent["thought"] == "Fallback: medium message, treating as general query"

@pytest.mark.asyncio
@patch('src.router.intent_parser.get_dynamic_system_prompt', return_value="dummy_sys_prompt")
@patch('src.llm.gateway.complete')
async def test_parse_intent_llm_throws_exception_triggering_fallback(mock_complete, mock_get_sys):
    mock_complete.side_effect = Exception("API Server down")
    
    intent = await parse_intent("yo what is up")
    assert intent["tier"] == "fast"
    assert intent["action"] == "social"
    assert intent["thought"] == "Social greeting"

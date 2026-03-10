"""
src/config/models.py — Model tier configuration for OpenRouter
"""

from typing import Optional

MODEL_TIERS: dict = {
    "lightweight": {
        "primary": "meta-llama/llama-3.1-8b-instruct",
        "fallback": "mistralai/mistral-7b-instruct:free",
        "tasks": ["classification", "simple_qa", "formatting", "intent_parsing"],
        "max_tokens": 1024,
    },
    "balanced": {
        "primary": "meta-llama/llama-3.1-8b-instruct",
        "fallback": "mistralai/mixtral-8x7b-instruct",
        "tasks": ["email_drafting", "summarization", "data_extraction", "calendar_parsing"],
        "max_tokens": 2048,
    },
    "capable": {
        "primary": "meta-llama/llama-3.1-70b-instruct",
        "fallback": "meta-llama/llama-3-70b-instruct",
        "tasks": ["research", "complex_reasoning", "planning", "creative_writing"],
        "max_tokens": 4096,
    },
    "system": {
        "primary": "google/gemma-2-9b-it",
        "fallback": None,
        "tasks": ["fact_extraction", "summarization_internal"],
        "max_tokens": 1024,
    },
}

RATE_LIMITS: dict = {
    "requests_per_minute": 10,
    "requests_per_hour": 100,
    "max_concurrent": 2,
    "cooldown_on_429": 60,  # seconds
}


def get_model_for_tier(tier: str) -> tuple[str, Optional[str]]:
    """Return (primary, fallback) model names for the given tier."""
    config = MODEL_TIERS.get(tier, MODEL_TIERS["lightweight"])
    return config["primary"], config.get("fallback")


def get_max_tokens_for_tier(tier: str) -> int:
    config = MODEL_TIERS.get(tier, MODEL_TIERS["lightweight"])
    return config.get("max_tokens", 1024)

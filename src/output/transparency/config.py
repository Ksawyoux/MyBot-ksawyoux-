from typing import Dict, Any
from src.output.core.envelope import TransparencyConfig
from src.output.core.types import TransparencyTier

def get_default_config() -> TransparencyConfig:
    return TransparencyConfig(
        default_tier=TransparencyTier.STANDARD,
        overrides={
            "simple_qa": TransparencyTier.SILENT,
            "email_operations": TransparencyTier.STANDARD,
            "financial_tasks": TransparencyTier.VERBOSE,
            "scheduled_tasks": TransparencyTier.STANDARD
        }
    )

def apply_tier_settings(config: TransparencyConfig, tier: TransparencyTier) -> TransparencyConfig:
    """Applies specific fine-grained settings based on the tier."""
    if tier == TransparencyTier.SILENT:
        config.show_reasoning = False
        config.show_tool_calls = False
        config.show_token_usage = False
        config.show_execution_time = False
        config.collapse_metadata = True
    elif tier == TransparencyTier.STANDARD:
        config.show_reasoning = False
        config.show_tool_calls = True
        config.show_token_usage = False
        config.show_execution_time = True
        config.collapse_metadata = True
    elif tier == TransparencyTier.VERBOSE:
        config.show_reasoning = True
        config.show_tool_calls = True
        config.show_token_usage = True
        config.show_execution_time = True
        config.collapse_metadata = False
    return config

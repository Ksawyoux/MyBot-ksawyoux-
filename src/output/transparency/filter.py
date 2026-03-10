from src.output.core.envelope import OutputEnvelope, TransparencyConfig
from src.output.core.types import TransparencyTier
from src.output.transparency.config import apply_tier_settings
from src.output.transparency.tier_resolver import resolve_tier

def filter_envelope(envelope: OutputEnvelope, user_config: TransparencyConfig) -> OutputEnvelope:
    """
    Modifies an OutputEnvelope in-place to strip out information
    that the user should not see based on their transparency tier.
    """
    tier = resolve_tier(envelope, user_config)
    
    # Apply settings for this specific tier
    config = apply_tier_settings(user_config.model_copy(), tier)
    
    transparency = envelope.transparency
    
    if not config.show_reasoning:
        transparency.reasoning = None
        
    if not config.show_tool_calls and transparency.execution_trace:
        # Strip details but keep high level steps
        for step in transparency.execution_trace.steps:
            step.details.clear()
            
    if tier == TransparencyTier.SILENT:
        # Hide the entire trace
        transparency.execution_trace = None
        
    if not config.show_token_usage:
        transparency.resources_used.pop("tokens", None)
        transparency.resources_used.pop("cost", None)
        
    if not config.show_execution_time:
        transparency.resources_used.pop("time", None)
        
    if not config.show_confidence_scores:
        transparency.confidence = None
        
    envelope.rendering.collapse_metadata = config.collapse_metadata
    
    return envelope

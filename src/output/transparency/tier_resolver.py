from src.output.core.envelope import OutputEnvelope, TransparencyConfig
from src.output.core.types import TransparencyTier, TaskStatus

def resolve_tier(envelope: OutputEnvelope, user_config: TransparencyConfig) -> TransparencyTier:
    """
    Determines the final transparency tier for a given task,
    taking into account overrides, rules, and user preferences.
    """
    tier = user_config.default_tier
    
    # 1. Check per-task-type override
    task_type_str = str(envelope.type.value)
    if task_type_str in user_config.overrides:
        tier = user_config.overrides[task_type_str]
        
    # 2. Conditional rule: Requires approval
    if envelope.interactions.required_action:
        if tier == TransparencyTier.SILENT:
            tier = TransparencyTier.STANDARD
            
    # 3. Conditional rule: Task failed
    if envelope.state.status == TaskStatus.FAILED:
        tier = TransparencyTier.VERBOSE
        
    return tier

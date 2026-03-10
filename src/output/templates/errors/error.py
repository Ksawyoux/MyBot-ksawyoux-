from typing import Any, Dict, Optional, List

from src.output.core.envelope import OutputEnvelope, ContentBlock, ContentLayer, InteractionConfig, StateConfig
from src.output.core.types import OutputType, TaskCategory, TaskStatus, BlockType
from src.output.templates.base_template import BaseTemplate
from src.output.core.actions import Action

class ErrorTemplate(BaseTemplate):
    """Template for showing error messages"""
    def __init__(self, title: str, description: str, task_id: Optional[str] = None, recoverable: bool = False, recovery_actions: Optional[List[Action]] = None):
        self.title = title
        self.description = description
        self.task_id = task_id
        self.recoverable = recoverable
        self.recovery_actions = recovery_actions or []
        
    def render(self, transparency_tier=None, user_context=None) -> OutputEnvelope:
        content = f"\u274c {self.title}\n\n{self.description}"
        status = TaskStatus.AWAITING_RETRY if self.recoverable else TaskStatus.FAILED
        
        return OutputEnvelope(
            task_id=self.task_id,
            type=OutputType.ERROR,
            category=TaskCategory.SYSTEM,
            content=ContentLayer(
                primary=ContentBlock(block_type=BlockType.TEXT, text=content)
            ),
            state=StateConfig(
                status=status,
                is_final=not self.recoverable
            ),
            interactions=InteractionConfig(
                quick_actions=self.recovery_actions
            )
        )

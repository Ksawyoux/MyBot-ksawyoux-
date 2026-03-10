from typing import Any, Dict, Optional, List
from datetime import datetime

from src.output.core.envelope import OutputEnvelope, ContentBlock, ContentLayer, InteractionConfig, StateConfig
from src.output.core.types import OutputType, TaskCategory, TaskStatus, BlockType
from src.output.templates.base_template import BaseTemplate
from src.output.core.actions import Action

class SimpleAnswerTemplate(BaseTemplate):
    """Basic Q&A or fact response"""
    def __init__(self, text: str, task_id: Optional[str] = None, quick_actions: Optional[List[Action]] = None):
        self.text = text
        self.task_id = task_id
        self.quick_actions = quick_actions or []
        
    def render(self, transparency_tier=None, user_context=None) -> OutputEnvelope:
        return OutputEnvelope(
            task_id=self.task_id,
            type=OutputType.RESPONSE,
            category=TaskCategory.SIMPLE,
            content=ContentLayer(
                primary=ContentBlock(block_type=BlockType.TEXT, text=self.text)
            ),
            state=StateConfig(
                status=TaskStatus.COMPLETED,
                is_final=True
            ),
            interactions=InteractionConfig(
                quick_actions=self.quick_actions
            )
        )

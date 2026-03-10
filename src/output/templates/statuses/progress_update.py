from typing import Any, Dict, Optional

from src.output.core.envelope import OutputEnvelope, ContentBlock, ContentLayer, InteractionConfig, StateConfig
from src.output.core.types import OutputType, TaskCategory, TaskStatus, BlockType, ProgressStyle
from src.output.templates.base_template import BaseTemplate
from src.output.core.actions import ProgressIndicator

class ProgressUpdateTemplate(BaseTemplate):
    """Template for showing task progress"""
    def __init__(self, status_text: str, task_id: str, current_step: Optional[int] = None, total_steps: Optional[int] = None):
        self.status_text = status_text
        self.task_id = task_id
        self.current_step = current_step
        self.total_steps = total_steps
        
    def render(self, transparency_tier=None, user_context=None) -> OutputEnvelope:
        progress = ProgressIndicator(
            style=ProgressStyle.STEPS,
            status_text=self.status_text,
            current_step=self.current_step,
            total_steps=self.total_steps
        )
        
        return OutputEnvelope(
            task_id=self.task_id,
            type=OutputType.STATUS,
            category=TaskCategory.COMPLEX,
            content=ContentLayer(
                primary=ContentBlock(block_type=BlockType.TEXT, text=self.status_text)
            ),
            state=StateConfig(
                status=TaskStatus.IN_PROGRESS,
                progress=progress,
                is_final=False
            )
        )

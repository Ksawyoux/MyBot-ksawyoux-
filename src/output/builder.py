from typing import Optional, List, Dict, Any

from src.output.core.envelope import (
    OutputEnvelope, ContentLayer, ContentBlock, StateConfig, 
    InteractionConfig, TransparencyLayer, RenderingHints
)
from src.output.core.types import (
    OutputType, TaskCategory, TaskStatus, BlockType, FormatStyle, ProgressStyle
)
from src.output.core.actions import Action, ProgressIndicator

class OutputBuilder:
    """Fluent API for constructing OutputEnvelopes"""
    
    def __init__(self):
        self._envelope = OutputEnvelope(
            content=ContentLayer(
                primary=ContentBlock(block_type=BlockType.TEXT, text="")
            ),
            state=StateConfig(status=TaskStatus.COMPLETED)
        )
        
    def task_id(self, task_id: str) -> 'OutputBuilder':
        self._envelope.task_id = task_id
        return self
        
    def type(self, output_type: OutputType | str) -> 'OutputBuilder':
        if isinstance(output_type, str):
            output_type = OutputType(output_type)
        self._envelope.type = output_type
        return self
        
    def category(self, category: TaskCategory | str) -> 'OutputBuilder':
        if isinstance(category, str):
            category = TaskCategory(category)
        self._envelope.category = category
        return self
        
    def content_text(self, text: str) -> 'OutputBuilder':
        self._envelope.content.primary.text = text
        return self
        
    def add_supplementary(self, block: ContentBlock) -> 'OutputBuilder':
        self._envelope.content.supplementary.append(block)
        return self
        
    def add_action(self, action: Action) -> 'OutputBuilder':
        self._envelope.interactions.quick_actions.append(action)
        return self
        
    def required_action(self, action: Action) -> 'OutputBuilder':
        self._envelope.interactions.required_action = action
        return self
        
    def mark_final(self) -> 'OutputBuilder':
        self._envelope.state.is_final = True
        return self
        
    def status(self, status: TaskStatus | str) -> 'OutputBuilder':
        if isinstance(status, str):
            status = TaskStatus(status)
        self._envelope.state.status = status
        return self
        
    def progress(self, current_step: int, total_steps: int, text: str, style: ProgressStyle = ProgressStyle.STEPS) -> 'OutputBuilder':
        self._envelope.state.progress = ProgressIndicator(
            style=style,
            current_step=current_step,
            total_steps=total_steps,
            status_text=text
        )
        return self
        
    def metadata(self, **kwargs) -> 'OutputBuilder':
        self._envelope.metadata.update(kwargs)
        return self
        
    def reasoning(self, text: str) -> 'OutputBuilder':
        self._envelope.transparency.reasoning = text
        return self
        
    def resource_metrics(self, **kwargs) -> 'OutputBuilder':
        self._envelope.transparency.resources_used.update(kwargs)
        return self
        
    def build(self) -> OutputEnvelope:
        """Returns the constructed OutputEnvelope"""
        return self._envelope

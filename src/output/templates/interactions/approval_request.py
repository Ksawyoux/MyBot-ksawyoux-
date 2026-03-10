from typing import Any, Dict, Optional

from src.output.core.envelope import OutputEnvelope, ContentBlock, ContentLayer, InteractionConfig, StateConfig
from src.output.core.types import OutputType, TaskCategory, TaskStatus, BlockType, ActionType
from src.output.templates.base_template import BaseTemplate
from src.output.core.actions import Action, ActionHandler

class ApprovalRequestTemplate(BaseTemplate):
    """Template for showing an approval request"""
    def __init__(
        self, 
        action_type: str, 
        target: str, 
        preview: Dict[str, Any], 
        risk_level: str, 
        task_id: str
    ):
        self.action_type = action_type
        self.target = target
        self.preview = preview
        self.risk_level = risk_level
        self.task_id = task_id
        
    def render(self, transparency_tier=None, user_context=None) -> OutputEnvelope:
        preview_text = "\n".join(f"{k}: {v}" for k, v in self.preview.items())
        text = f"\U0001f4e7 Approval Required\n\nAction: {self.action_type}\nTarget: {self.target}\n\nPreview:\n{preview_text}\n\nRisk Level: {self.risk_level}"
        
        return OutputEnvelope(
            task_id=self.task_id,
            type=OutputType.APPROVAL,
            category=TaskCategory.COMPLEX,
            content=ContentLayer(
                primary=ContentBlock(block_type=BlockType.TEXT, text=text)
            ),
            state=StateConfig(
                status=TaskStatus.AWAITING_INPUT,
                is_final=False
            ),
            interactions=InteractionConfig(
                required_action=Action(
                    action_id=f"approve_{self.task_id}",
                    action_type=ActionType.CALLBACK,
                    label="\u2705 Approve",
                    handler=ActionHandler(callback_data=f"approve:{self.task_id}")
                ),
                quick_actions=[
                    Action(
                        action_id=f"reject_{self.task_id}",
                        action_type=ActionType.CALLBACK,
                        label="\u274c Reject",
                        handler=ActionHandler(callback_data=f"reject:{self.task_id}")
                    )
                ]
            )
        )

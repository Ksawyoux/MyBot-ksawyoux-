from __future__ import annotations
from typing import List, Optional, Any, Dict
from datetime import datetime
from pydantic import BaseModel, Field

from src.output.core.types import ActionType, ActionStyle, ProgressStyle, StepStatus

class InputSchema(BaseModel):
    """Schema for user input collection"""
    fields: Dict[str, Any]
    required: List[str]

class ActionHandler(BaseModel):
    """Defines how an action is handled"""
    callback_data: Optional[str] = None # For Telegram callbacks
    url: Optional[str] = None           # For external links
    command: Optional[str] = None       # For bot commands
    input_schema: Optional[InputSchema] = None # For user input

class Action(BaseModel):
    """User interaction element (e.g. inline button)"""
    action_id: str
    action_type: ActionType
    
    # Display
    label: str
    icon: Optional[str] = None
    style: ActionStyle = ActionStyle.PRIMARY
    
    # Behavior
    handler: ActionHandler = Field(default_factory=ActionHandler)
    
    # State
    enabled: bool = True
    loading_text: Optional[str] = None
    confirmation_required: bool = False
    confirmation_text: Optional[str] = None

class ProgressIndicator(BaseModel):
    """Progress tracker for long-running tasks"""
    style: ProgressStyle
    
    # For percentage style
    current: Optional[int] = None # 0-100
    
    # For steps style
    current_step: Optional[int] = None
    total_steps: Optional[int] = None
    step_descriptions: Optional[List[str]] = None
    
    # For ETA style
    estimated_completion: Optional[datetime] = None
    started_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Common
    status_text: str
    cancelable: bool = False

class ExecutionStep(BaseModel):
    """A single step in the agent execution trace"""
    step_number: int
    description: str
    status: StepStatus = StepStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Details (only in verbose mode)
    details: Dict[str, Any] = Field(default_factory=dict)
    
    # Nested sub-steps
    sub_steps: Optional[List['ExecutionStep']] = None

class ExecutionTrace(BaseModel):
    """Complete execution trace for a task"""
    steps: List[ExecutionStep] = Field(default_factory=list)

ExecutionStep.model_rebuild()

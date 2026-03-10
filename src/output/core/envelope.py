import uuid
from typing import List, Optional, Any, Dict
from datetime import datetime
from pydantic import BaseModel, Field

from src.output.core.types import (
    OutputType, TaskCategory, TransparencyTier, FormatStyle, BlockType, ListStyle, BlockImportance
)
from src.output.core.actions import Action, ProgressIndicator, ExecutionTrace

class ListItem(BaseModel):
    """An item in a list block"""
    text: str
    checked: Optional[bool] = None # For checklists
    sub_items: Optional[List['ListItem']] = None

class MediaAttachment(BaseModel):
    """Media file attached to output"""
    url: Optional[str] = None
    file_path: Optional[str] = None
    file_name: str
    media_type: str # e.g. 'image/png', 'application/pdf'
    size_bytes: Optional[int] = None

class ContentBlock(BaseModel):
    """A building block for the rendered message content"""
    block_type: BlockType = BlockType.TEXT
    
    # Text block
    text: Optional[str] = None
    markdown_enabled: bool = True
    
    # List block
    items: Optional[List[ListItem]] = None
    list_style: ListStyle = ListStyle.BULLET
    
    # Table block
    headers: Optional[List[str]] = None
    rows: Optional[List[List[str]]] = None
    
    # Card block (rich formatting)
    title: Optional[str] = None
    subtitle: Optional[str] = None
    body: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    
    # Code block
    code: Optional[str] = None
    language: Optional[str] = None
    
    # Metadata
    importance: BlockImportance = BlockImportance.NORMAL
    collapsible: bool = False
    collapsed_preview: Optional[str] = None

class TransparencyConfig(BaseModel):
    """Controls what information is visible to the user"""
    default_tier: TransparencyTier = TransparencyTier.STANDARD
    overrides: Dict[str, TransparencyTier] = Field(default_factory=dict)
    
    show_reasoning: bool = False
    show_tool_calls: bool = False
    show_token_usage: bool = False
    show_execution_time: bool = False
    show_confidence_scores: bool = False
    collapse_metadata: bool = True

class InteractionConfig(BaseModel):
    """Configuration for user interactions"""
    quick_actions: List[Action] = Field(default_factory=list)
    required_action: Optional[Action] = None
    followup_suggestions: List[str] = Field(default_factory=list)

class StateConfig(BaseModel):
    """Current state of the output task"""
    status: str # from TaskStatus
    progress: Optional[ProgressIndicator] = None
    is_final: bool = False
    is_editable: bool = False
    expires_at: Optional[datetime] = None

class TransparencyLayer(BaseModel):
    """Detailed execution information for verbose tiers"""
    reasoning: Optional[str] = None
    execution_trace: Optional[ExecutionTrace] = None
    resources_used: Dict[str, Any] = Field(default_factory=dict) # e.g. {"tokens": 100}
    confidence: Optional[float] = None

class RenderingHints(BaseModel):
    """Hints for platform renderers"""
    format_style: FormatStyle = FormatStyle.STANDARD
    collapse_by_default: List[str] = Field(default_factory=list)
    highlight_sections: List[str] = Field(default_factory=list)
    platform_overrides: Dict[str, Any] = Field(default_factory=dict)
    collapse_metadata: bool = True

class ContentLayer(BaseModel):
    """The actual content of the message"""
    primary: ContentBlock
    supplementary: List[ContentBlock] = Field(default_factory=list)
    media: List[MediaAttachment] = Field(default_factory=list)

class OutputEnvelope(BaseModel):
    """Universal output wrapper for all bot responses"""
    # Core Identification
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_id: Optional[str] = None
    conversation_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    sequence_number: int = 1
    
    # Message Classification
    type: OutputType = OutputType.RESPONSE
    category: TaskCategory = TaskCategory.SIMPLE
    priority: int = 0
    
    # Content Payload
    content: ContentLayer
    
    # User Interaction
    interactions: InteractionConfig = Field(default_factory=InteractionConfig)
    
    # State Management
    state: StateConfig
    
    # Transparency Layer
    transparency: TransparencyLayer = Field(default_factory=TransparencyLayer)
    
    # Rendering Hints
    rendering: RenderingHints = Field(default_factory=RenderingHints)
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)

ListItem.model_rebuild()

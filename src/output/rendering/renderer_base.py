from abc import ABC, abstractmethod
from typing import Any

from src.output.core.envelope import OutputEnvelope
from src.output.core.types import TransparencyTier

class RenderedMessage(ABC):
    """Abstract representation of a rendered message for a specific platform"""
    pass

class BaseRenderer(ABC):
    """Abstract base class for platform-specific renderers"""
    
    def __init__(self, user_transparency_tier: TransparencyTier = TransparencyTier.STANDARD):
        self.user_transparency_tier = user_transparency_tier
        
    @abstractmethod
    def render(self, envelope: OutputEnvelope) -> RenderedMessage:
        """Render the output envelope to platform-specific format"""
        pass

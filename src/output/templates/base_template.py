from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from src.output.core.envelope import OutputEnvelope
from src.output.core.types import TransparencyTier

class BaseTemplate(ABC):
    """Abstract base class for all output templates"""
    
    @abstractmethod
    def render(self, transparency_tier: TransparencyTier = TransparencyTier.STANDARD, user_context: Optional[Dict[str, Any]] = None) -> OutputEnvelope:
        """Generate an OutputEnvelope from this template"""
        pass

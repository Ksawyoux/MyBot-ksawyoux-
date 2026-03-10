"""
src/llm/model_router.py — Map task tiers to concrete model names
"""

from src.config.models import get_model_for_tier, get_max_tokens_for_tier
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ModelRouter:
    """Routes a tier name to primary/fallback model strings."""

    def get_models(self, tier: str) -> tuple[str, str | None]:
        primary, fallback = get_model_for_tier(tier)
        logger.debug("Tier '%s' → primary=%s fallback=%s", tier, primary, fallback)
        return primary, fallback

    def get_max_tokens(self, tier: str) -> int:
        return get_max_tokens_for_tier(tier)


# Module-level singleton
_router = ModelRouter()


def get_model_router() -> ModelRouter:
    return _router

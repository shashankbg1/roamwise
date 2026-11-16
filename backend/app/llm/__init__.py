"""Model backends."""

from app.config import Settings
from app.llm.base import LLMError, LLMProvider

__all__ = ["LLMError", "LLMProvider", "build_provider"]


def build_provider(settings: Settings) -> LLMProvider:
    """Create the provider named in settings. Imports are local so the mock needs no SDK."""
    if settings.llm_provider == "mock":
        from app.llm.mock import MockProvider

        return MockProvider()
    from app.llm.anthropic_provider import AnthropicProvider

    region = settings.aws_region if settings.llm_provider == "bedrock" else None
    return AnthropicProvider(settings.llm_model, bedrock_region=region)

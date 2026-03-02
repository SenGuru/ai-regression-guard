"""
LLM provider implementations.
"""
from .base import BaseProvider
from .openai_provider import OpenAIProvider
from .anthropic_provider import AnthropicProvider
from .fake import FakeProvider, FakeJudgeProvider

__all__ = [
    "BaseProvider",
    "OpenAIProvider",
    "AnthropicProvider",
    "FakeProvider",
    "FakeJudgeProvider",
]


def get_provider(provider_name: str, model: str) -> BaseProvider:
    """
    Factory function to get a provider instance.

    Args:
        provider_name: Provider name ("openai", "anthropic", "fake")
        model: Model name

    Returns:
        Provider instance

    Raises:
        ValueError: If provider_name is not recognized
    """
    if provider_name == "openai":
        return OpenAIProvider(model=model)
    elif provider_name == "anthropic":
        return AnthropicProvider(model=model)
    elif provider_name == "fake":
        return FakeProvider()
    else:
        raise ValueError(
            f"Unknown provider: {provider_name}. "
            f"Supported: openai, anthropic, fake"
        )

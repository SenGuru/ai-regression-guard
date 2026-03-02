"""
Anthropic provider implementation.
"""
import os
from .base import BaseProvider


class AnthropicProvider(BaseProvider):
    """Provider for Anthropic models."""

    def __init__(self, model: str = "claude-3-5-sonnet-20241022"):
        """
        Args:
            model: Model name (e.g., "claude-3-5-sonnet-20241022")
        """
        self.model = model
        self._client = None

    def _get_client(self):
        """Lazy-load Anthropic client."""
        if self._client is None:
            try:
                from anthropic import Anthropic
            except ImportError:
                raise ImportError(
                    "anthropic package not installed. Install with: pip install anthropic"
                )

            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError(
                    "ANTHROPIC_API_KEY environment variable not set"
                )

            self._client = Anthropic(api_key=api_key)

        return self._client

    def generate(self, prompt: str) -> str:
        """Generate response using Anthropic."""
        client = self._get_client()

        response = client.messages.create(
            model=self.model,
            max_tokens=1024,
            temperature=0.0,  # Deterministic for testing
            messages=[{"role": "user", "content": prompt}]
        )

        return response.content[0].text

    @property
    def name(self) -> str:
        return f"anthropic/{self.model}"

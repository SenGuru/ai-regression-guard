"""
OpenAI provider implementation.
"""
import os
from .base import BaseProvider


class OpenAIProvider(BaseProvider):
    """Provider for OpenAI models."""

    def __init__(self, model: str = "gpt-4"):
        """
        Args:
            model: Model name (e.g., "gpt-4", "gpt-3.5-turbo")
        """
        self.model = model
        self._client = None

    def _get_client(self):
        """Lazy-load OpenAI client."""
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError:
                raise ImportError(
                    "openai package not installed. Install with: pip install openai"
                )

            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                raise ValueError(
                    "OPENAI_API_KEY environment variable not set"
                )

            self._client = OpenAI(api_key=api_key)

        return self._client

    def generate(self, prompt: str) -> str:
        """Generate response using OpenAI."""
        client = self._get_client()

        response = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,  # Deterministic for testing
        )

        return response.choices[0].message.content

    @property
    def name(self) -> str:
        return f"openai/{self.model}"

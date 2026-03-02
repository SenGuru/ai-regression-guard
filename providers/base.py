"""
Base provider interface for LLM calls.
"""
from abc import ABC, abstractmethod


class BaseProvider(ABC):
    """Base class for LLM providers."""

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """
        Generate a response from the LLM.

        Args:
            prompt: The prompt to send to the LLM

        Returns:
            The generated text response

        Raises:
            Exception: If the API call fails
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name for logging/debugging."""
        pass

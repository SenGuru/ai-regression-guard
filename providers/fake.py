"""
Fake provider for testing without real API calls.
"""
import json
from .base import BaseProvider


class FakeProvider(BaseProvider):
    """
    Fake provider for testing.

    Returns predictable JSON responses based on input text.
    """

    def __init__(self, responses: dict[str, str] | None = None):
        """
        Args:
            responses: Optional dict mapping prompt substrings to responses.
                       If None, uses default classification logic.
        """
        self.responses = responses or {}
        self.call_count = 0
        self.last_prompt = None

    def generate(self, prompt: str) -> str:
        """Generate fake response."""
        self.call_count += 1
        self.last_prompt = prompt

        # Check for custom responses
        for key, response in self.responses.items():
            if key.lower() in prompt.lower():
                return response

        # Default: simple classification logic
        prompt_lower = prompt.lower()

        if "payment" in prompt_lower or "billing" in prompt_lower or "pay" in prompt_lower:
            category = "billing"
            priority = "high"
        elif "api" in prompt_lower or "error" in prompt_lower or "technical" in prompt_lower:
            category = "technical"
            priority = "medium"
        elif "account" in prompt_lower or "email" in prompt_lower or "update" in prompt_lower:
            category = "account"
            priority = "low"
        else:
            category = "other"
            priority = "low"

        # Extract a simple summary from prompt
        summary = prompt[:50] if len(prompt) < 50 else prompt[:47] + "..."

        response = {
            "category": category,
            "priority": priority,
            "summary": summary
        }

        return json.dumps(response)

    @property
    def name(self) -> str:
        return "fake/test-model"


class FakeJudgeProvider(BaseProvider):
    """
    Fake judge provider for testing LLM-as-a-judge.

    Returns deterministic judge scores in strict JSON format.
    """

    def __init__(self, default_score: float = 0.9, default_reason: str = "passes rubric"):
        """
        Args:
            default_score: Default score to return (0.0 to 1.0)
            default_reason: Default reason string
        """
        self.default_score = default_score
        self.default_reason = default_reason
        self.call_count = 0
        self.last_prompt = None

    def generate(self, prompt: str) -> str:
        """Generate fake judge response in strict JSON format."""
        self.call_count += 1
        self.last_prompt = prompt

        # Check for specific test scenarios in prompt
        prompt_lower = prompt.lower()

        # Detect quality issues
        if "parse_error" in prompt_lower or "invalid json" in prompt_lower:
            score = 0.2
            reason = "output has parse errors"
        elif "refusal" in prompt_lower or "cannot help" in prompt_lower:
            score = 0.1
            reason = "model refused task"
        elif "hallucination" in prompt_lower or "factually incorrect" in prompt_lower:
            score = 0.3
            reason = "contains hallucinations"
        else:
            score = self.default_score
            reason = self.default_reason

        # Return strict JSON format
        response = {
            "score": score,
            "reason": reason
        }

        return json.dumps(response)

    @property
    def name(self) -> str:
        return "fake/judge-model"

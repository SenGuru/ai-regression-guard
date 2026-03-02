"""
Scoring logic for AI outputs.
Pure functions and simple classes only.
"""
import json
from abc import ABC, abstractmethod
from typing import Any, Optional
from .judge_cache import JudgeCache


class BaseScorer(ABC):
    """Base class for all scorers."""

    name: str

    @abstractmethod
    def score(self, output: str | dict, context: dict | None = None) -> float:
        """
        Score an output.

        Args:
            output: The LLM output to score (string or dict)
            context: Optional context (e.g., expected schema, metadata)

        Returns:
            float between 0.0 and 1.0 (higher is better)
        """
        pass


class RefusalScorer(BaseScorer):
    """
    Detects if the LLM refused or errored.
    Returns 0.0 if refusal detected, 1.0 otherwise.
    """

    name = "refusal_detection"

    REFUSAL_PATTERNS = [
        "i cannot",
        "i can't",
        "i'm not able to",
        "i am not able to",
        "sorry, i cannot",
        "i apologize, but i cannot",
        "as an ai",
        "as a language model",
        "i don't have access",
        "i don't have the ability",
    ]

    def score(self, output: str | dict, context: dict | None = None) -> float:
        """Return 0.0 if refusal detected, else 1.0."""
        text = output if isinstance(output, str) else json.dumps(output)
        text_lower = text.lower()

        for pattern in self.REFUSAL_PATTERNS:
            if pattern in text_lower:
                return 0.0

        return 1.0


class JsonSchemaScorer(BaseScorer):
    """
    Validates JSON output against a simple schema.
    Returns partial credit based on how many requirements are met.

    Schema format:
    {
        "category": {"type": "string", "enum": ["billing", "technical"]},
        "priority": {"type": "string", "enum": ["low", "high"]},
        "summary": {"type": "string", "required": True}
    }
    """

    name = "json_schema"

    def __init__(self, schema: dict[str, dict[str, Any]]):
        """
        Args:
            schema: Simple schema dict mapping field names to constraints
        """
        self.schema = schema

    def score(self, output: str | dict, context: dict | None = None) -> float:
        """Return 0..1 based on schema adherence."""

        # Parse JSON if needed
        if isinstance(output, str):
            try:
                data = json.loads(output)
            except json.JSONDecodeError:
                return 0.0
        else:
            data = output

        if not isinstance(data, dict):
            return 0.0

        # Score each field
        total_fields = len(self.schema)
        if total_fields == 0:
            return 1.0

        points = 0.0

        for field_name, constraints in self.schema.items():
            field_value = data.get(field_name)

            # Check if field exists
            if field_value is None:
                continue

            # Check type
            expected_type = constraints.get("type")
            if expected_type:
                if expected_type == "string" and not isinstance(field_value, str):
                    continue
                if expected_type == "number" and not isinstance(field_value, (int, float)):
                    continue
                if expected_type == "boolean" and not isinstance(field_value, bool):
                    continue

            # Check enum constraint
            enum_values = constraints.get("enum")
            if enum_values and field_value not in enum_values:
                continue

            # Check non-empty for strings
            if isinstance(field_value, str) and len(field_value.strip()) == 0:
                continue

            # Field passed all checks
            points += 1.0

        return points / total_fields


class CompositeScorer(BaseScorer):
    """
    Combines multiple scorers with optional weights.
    Returns weighted average of all scorer outputs.
    """

    name = "composite"

    def __init__(self, scorers: list[BaseScorer], weights: list[float] | None = None):
        """
        Args:
            scorers: List of scorer instances
            weights: Optional weights (must sum to 1.0). If None, uses equal weights.
        """
        if not scorers:
            raise ValueError("Must provide at least one scorer")

        self.scorers = scorers

        if weights is None:
            self.weights = [1.0 / len(scorers)] * len(scorers)
        else:
            if len(weights) != len(scorers):
                raise ValueError("Number of weights must match number of scorers")
            if abs(sum(weights) - 1.0) > 1e-6:
                raise ValueError("Weights must sum to 1.0")
            self.weights = weights

    def score(self, output: str | dict, context: dict | None = None) -> float:
        """Return weighted average of all scorer outputs."""
        total = 0.0
        for scorer, weight in zip(self.scorers, self.weights):
            total += scorer.score(output, context) * weight
        return total

    def score_detailed(self, output: str | dict, context: dict | None = None) -> dict[str, float]:
        """
        Return detailed breakdown of scores per scorer.

        Returns:
            Dict mapping scorer name to individual score (not weighted)
        """
        breakdown = {}
        for scorer in self.scorers:
            breakdown[scorer.name] = scorer.score(output, context)
        return breakdown


class ContainsScorer(BaseScorer):
    """
    Checks if output contains expected phrases.
    Returns partial credit based on how many expected phrases are present.

    Requires context["expected_contains"] list.
    """

    name = "contains"

    def score(self, output: str | dict, context: dict | None = None) -> float:
        """Return 0..1 based on how many expected phrases are found."""
        if not context or "expected_contains" not in context:
            return 1.0  # No requirements = pass

        expected = context.get("expected_contains", [])
        if not expected:
            return 1.0

        # Convert output to text
        text = output if isinstance(output, str) else json.dumps(output)
        text_lower = text.lower()

        # Count how many expected phrases are present
        found = 0
        for phrase in expected:
            if phrase.lower() in text_lower:
                found += 1

        return found / len(expected)


class NotContainsScorer(BaseScorer):
    """
    Checks if output contains forbidden phrases.
    Returns 0.0 if any forbidden phrase appears, else 1.0.

    Requires context["expected_not_contains"] list.
    """

    name = "not_contains"

    def score(self, output: str | dict, context: dict | None = None) -> float:
        """Return 0.0 if any forbidden phrase is found, else 1.0."""
        if not context or "expected_not_contains" not in context:
            return 1.0  # No restrictions = pass

        forbidden = context.get("expected_not_contains", [])
        if not forbidden:
            return 1.0

        # Convert output to text
        text = output if isinstance(output, str) else json.dumps(output)
        text_lower = text.lower()

        # Check for any forbidden phrases
        for phrase in forbidden:
            if phrase.lower() in text_lower:
                return 0.0

        return 1.0


class LLMJudgeScorer(BaseScorer):
    """
    Uses an LLM to judge output quality based on a rubric.

    CRITICAL SAFETY FEATURES:
    - Caches results to avoid redundant API calls
    - Strict JSON parsing with safe fallback
    - Deterministic (temperature=0)
    - Never crashes on errors
    """

    name = "llm_judge"

    JUDGE_PROMPT_TEMPLATE = """You are an expert evaluator. Score the following AI output based on the rubric.

INPUT:
{input}

OUTPUT TO JUDGE:
{output}

RUBRIC:
{rubric}

Respond with ONLY valid JSON in this exact format (no other text):
{{
  "score": <float between 0.0 and 1.0>,
  "reason": "<concise explanation, max 200 characters>"
}}"""

    def __init__(
        self,
        judge_provider,  # BaseProvider instance
        run_id: str,
        cache_dir: str = ".judge_cache",
        enable_cache: bool = True
    ):
        """
        Args:
            judge_provider: Provider instance to use as judge
            run_id: Run identifier for cache key
            cache_dir: Directory for judge cache
            enable_cache: Whether to use caching
        """
        self.judge_provider = judge_provider
        self.run_id = run_id
        self.enable_cache = enable_cache
        self.cache = JudgeCache(cache_dir) if enable_cache else None
        self.last_judge_reason: Optional[str] = None

    def _parse_judge_response(self, response: str) -> tuple[float, str]:
        """
        Parse judge response with strict error handling.

        Returns:
            (score, reason) tuple. On error: (0.0, "judge_parse_error")
        """
        try:
            data = json.loads(response.strip())

            if not isinstance(data, dict):
                return 0.0, "judge_parse_error"

            if "score" not in data or "reason" not in data:
                return 0.0, "judge_parse_error"

            score = float(data["score"])
            reason = str(data["reason"])[:200]  # Enforce 200 char limit

            # Validate score range
            if not (0.0 <= score <= 1.0):
                return 0.0, "judge_parse_error"

            return score, reason

        except (json.JSONDecodeError, ValueError, KeyError):
            return 0.0, "judge_parse_error"

    def score(self, output: str | dict, context: dict | None = None) -> float:
        """
        Score output using LLM judge with caching.

        Requires context["case_id"], context["rubric"], context["input"]
        """
        if not context:
            return 0.0

        case_id = context.get("case_id", "unknown")
        rubric = context.get("rubric", "")
        input_data = context.get("input", {})

        if not rubric:
            # No rubric = skip judge scoring
            return 1.0

        # Convert output to text
        output_text = output if isinstance(output, str) else json.dumps(output)

        # Check cache first
        if self.enable_cache and self.cache:
            cached = self.cache.get(
                run_id=self.run_id,
                case_id=case_id,
                output_text=output_text,
                rubric=rubric,
                judge_provider=self.judge_provider.name,
                judge_model=self.judge_provider.name
            )
            if cached:
                self.last_judge_reason = cached["reason"]
                return cached["score"]

        # Build judge prompt
        input_str = json.dumps(input_data) if isinstance(input_data, dict) else str(input_data)

        prompt = self.JUDGE_PROMPT_TEMPLATE.format(
            input=input_str,
            output=output_text,
            rubric=rubric
        )

        # Call judge (with error handling)
        try:
            response = self.judge_provider.generate(prompt)
            score, reason = self._parse_judge_response(response)

        except Exception:
            # Any error during judging: safe fallback
            score = 0.0
            reason = "judge_api_error"

        # Store reason for retrieval
        self.last_judge_reason = reason

        # Cache result
        if self.enable_cache and self.cache:
            self.cache.set(
                run_id=self.run_id,
                case_id=case_id,
                output_text=output_text,
                rubric=rubric,
                judge_provider=self.judge_provider.name,
                judge_model=self.judge_provider.name,
                score=score,
                reason=reason
            )

        return score

    def get_last_reason(self) -> Optional[str]:
        """Get the reason from the last judge evaluation."""
        return self.last_judge_reason

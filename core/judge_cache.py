"""
Judge cache for LLM-as-a-judge scoring.
Caches judge results to avoid redundant API calls and control costs.
"""
import hashlib
import json
from pathlib import Path
from typing import TypedDict, Optional


class JudgeResult(TypedDict):
    """Cached judge result."""
    score: float
    reason: str


class JudgeCache:
    """
    Cache for LLM judge results.

    Cache key includes: run_id, case_id, output_text, rubric, provider, model
    """

    def __init__(self, cache_dir: str = ".judge_cache"):
        """
        Args:
            cache_dir: Directory to store cache files
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)

    def _get_cache_key(
        self,
        run_id: str,
        case_id: str,
        output_text: str,
        rubric: str,
        judge_provider: str,
        judge_model: str
    ) -> str:
        """Generate cache key from inputs."""
        # Hash output_text to keep key length manageable
        output_hash = hashlib.sha256(output_text.encode()).hexdigest()[:16]
        rubric_hash = hashlib.sha256(rubric.encode()).hexdigest()[:16]

        # Combine all inputs
        key_parts = [
            run_id,
            case_id,
            output_hash,
            rubric_hash,
            judge_provider,
            judge_model
        ]

        key_string = "|".join(key_parts)
        return hashlib.sha256(key_string.encode()).hexdigest()

    def _get_cache_path(self, cache_key: str) -> Path:
        """Get file path for cache key."""
        return self.cache_dir / f"{cache_key}.json"

    def get(
        self,
        run_id: str,
        case_id: str,
        output_text: str,
        rubric: str,
        judge_provider: str,
        judge_model: str
    ) -> Optional[JudgeResult]:
        """
        Retrieve cached judge result.

        Returns:
            JudgeResult if found, None otherwise
        """
        cache_key = self._get_cache_key(
            run_id, case_id, output_text, rubric, judge_provider, judge_model
        )
        cache_path = self._get_cache_path(cache_key)

        if not cache_path.exists():
            return None

        try:
            with open(cache_path, "r") as f:
                data = json.load(f)

            return JudgeResult(
                score=data["score"],
                reason=data["reason"]
            )
        except (json.JSONDecodeError, KeyError, FileNotFoundError):
            # Cache file is corrupted, ignore it
            return None

    def set(
        self,
        run_id: str,
        case_id: str,
        output_text: str,
        rubric: str,
        judge_provider: str,
        judge_model: str,
        score: float,
        reason: str
    ) -> None:
        """
        Store judge result in cache.

        Args:
            run_id: Run identifier
            case_id: Case identifier
            output_text: Output being judged
            rubric: Judging rubric
            judge_provider: Judge provider name
            judge_model: Judge model name
            score: Judge score (0.0 to 1.0)
            reason: Judge reasoning
        """
        cache_key = self._get_cache_key(
            run_id, case_id, output_text, rubric, judge_provider, judge_model
        )
        cache_path = self._get_cache_path(cache_key)

        data = {
            "score": score,
            "reason": reason,
            # Store metadata for debugging
            "metadata": {
                "run_id": run_id,
                "case_id": case_id,
                "judge_provider": judge_provider,
                "judge_model": judge_model
            }
        }

        with open(cache_path, "w") as f:
            json.dump(data, f, indent=2)

    def clear(self) -> None:
        """Clear all cached results."""
        for cache_file in self.cache_dir.glob("*.json"):
            cache_file.unlink()

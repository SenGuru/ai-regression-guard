"""
Baseline storage and retrieval.
Simple file-based storage for v1.
"""
import json
from pathlib import Path
from typing import Any, TypedDict, Optional


class BaselineData(TypedDict):
    """Stored baseline data."""
    run_id: str
    output: str | dict
    score: float


class CaseScore(TypedDict):
    """Per-case score breakdown."""
    total: float
    scorers: dict[str, float]
    judge_reason: Optional[str]


class DetailedBaselineData(TypedDict):
    """Detailed baseline with per-case scores."""
    run_id: str
    overall_avg: float
    per_case_scores: dict[str, CaseScore]


class BaselineStore:
    """
    Simple file-based baseline storage.
    Stores baselines as JSON files in a directory.
    """

    def __init__(self, storage_dir: str = ".baselines"):
        """
        Args:
            storage_dir: Directory to store baseline files
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(exist_ok=True)

    def _get_baseline_path(self, run_id: str) -> Path:
        """Get file path for a run_id."""
        # Sanitize run_id for filesystem
        safe_id = run_id.replace("/", "_").replace("\\", "_")
        return self.storage_dir / f"{safe_id}.json"

    def store(self, run_id: str, output: str | dict, score: float) -> None:
        """
        Store a baseline result.

        Args:
            run_id: Unique identifier for this run (e.g., "checkout-agent-v3")
            output: The LLM output that produced this score
            score: The score for this output (0.0 to 1.0)
        """
        if not (0.0 <= score <= 1.0):
            raise ValueError(f"score must be between 0 and 1, got {score}")

        data: BaselineData = {
            "run_id": run_id,
            "output": output,
            "score": score
        }

        path = self._get_baseline_path(run_id)
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def get(self, run_id: str) -> BaselineData | None:
        """
        Retrieve a baseline result.

        Args:
            run_id: Unique identifier for the baseline

        Returns:
            BaselineData if found, None otherwise
        """
        path = self._get_baseline_path(run_id)
        if not path.exists():
            return None

        with open(path, "r") as f:
            data = json.load(f)

        return BaselineData(
            run_id=data["run_id"],
            output=data["output"],
            score=data["score"]
        )

    def exists(self, run_id: str) -> bool:
        """Check if a baseline exists."""
        return self._get_baseline_path(run_id).exists()

    def delete(self, run_id: str) -> bool:
        """
        Delete a baseline.

        Args:
            run_id: Unique identifier for the baseline

        Returns:
            True if deleted, False if not found
        """
        path = self._get_baseline_path(run_id)
        if path.exists():
            path.unlink()
            return True
        return False

    def store_detailed(
        self,
        run_id: str,
        overall_avg: float,
        per_case_scores: dict[str, CaseScore]
    ) -> None:
        """
        Store a detailed baseline with per-case scores.

        Args:
            run_id: Unique identifier for this run
            overall_avg: Overall average score across all cases
            per_case_scores: Dict mapping case_id to CaseScore
        """
        if not (0.0 <= overall_avg <= 1.0):
            raise ValueError(f"overall_avg must be between 0 and 1, got {overall_avg}")

        data: DetailedBaselineData = {
            "run_id": run_id,
            "overall_avg": overall_avg,
            "per_case_scores": per_case_scores
        }

        path = self._get_baseline_path(run_id)
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def get_detailed(self, run_id: str) -> Optional[DetailedBaselineData]:
        """
        Retrieve a detailed baseline with per-case scores.

        Args:
            run_id: Unique identifier for the baseline

        Returns:
            DetailedBaselineData if found, None otherwise
        """
        path = self._get_baseline_path(run_id)
        if not path.exists():
            return None

        with open(path, "r") as f:
            data = json.load(f)

        # Check if this is a detailed baseline
        if "per_case_scores" not in data:
            # Legacy baseline format - convert
            return None

        return DetailedBaselineData(
            run_id=data["run_id"],
            overall_avg=data["overall_avg"],
            per_case_scores=data["per_case_scores"]
        )

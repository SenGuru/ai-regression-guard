"""
Regression detection logic.
Compares baseline vs new scores and determines if quality regressed.
"""
from typing import TypedDict


class RegressionResult(TypedDict):
    """Result of a regression check."""
    baseline_score: float
    new_score: float
    delta: float
    is_regression: bool
    threshold: float


def detect_regression(
    baseline_score: float,
    new_score: float,
    threshold: float = 0.05
) -> RegressionResult:
    """
    Detect if new score represents a regression from baseline.

    A regression occurs when new_score is worse (lower) than baseline_score
    by more than the threshold.

    Args:
        baseline_score: Score from baseline version (0.0 to 1.0)
        new_score: Score from new version (0.0 to 1.0)
        threshold: Minimum delta to consider a regression (default 0.05)

    Returns:
        RegressionResult with scores, delta, and regression status

    Example:
        >>> result = detect_regression(0.9, 0.6, threshold=0.1)
        >>> result["is_regression"]
        True
        >>> result["delta"]
        -0.3
    """
    if not (0.0 <= baseline_score <= 1.0):
        raise ValueError(f"baseline_score must be between 0 and 1, got {baseline_score}")
    if not (0.0 <= new_score <= 1.0):
        raise ValueError(f"new_score must be between 0 and 1, got {new_score}")
    if threshold < 0:
        raise ValueError(f"threshold must be non-negative, got {threshold}")

    delta = new_score - baseline_score
    # Use small epsilon to handle floating point precision
    EPSILON = 1e-9
    is_regression = delta < (-threshold - EPSILON)

    return RegressionResult(
        baseline_score=baseline_score,
        new_score=new_score,
        delta=delta,
        is_regression=is_regression,
        threshold=threshold
    )


def should_fail_ci(result: RegressionResult) -> bool:
    """
    Determine if CI should fail based on regression result.

    Args:
        result: Result from detect_regression()

    Returns:
        True if CI should fail (regression detected)
    """
    return result["is_regression"]

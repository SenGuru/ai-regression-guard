"""
Tests for regression detection logic.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.regressions import detect_regression, should_fail_ci


def test_detect_regression_clear_regression():
    result = detect_regression(baseline_score=0.9, new_score=0.6, threshold=0.1)

    assert result["baseline_score"] == 0.9
    assert result["new_score"] == 0.6
    assert abs(result["delta"] - (-0.3)) < 1e-9
    assert result["is_regression"] is True
    assert result["threshold"] == 0.1


def test_detect_regression_no_regression():
    result = detect_regression(baseline_score=0.8, new_score=0.85, threshold=0.05)

    assert result["baseline_score"] == 0.8
    assert result["new_score"] == 0.85
    assert abs(result["delta"] - 0.05) < 1e-9
    assert result["is_regression"] is False


def test_detect_regression_within_threshold():
    # Small drop but within threshold
    result = detect_regression(baseline_score=0.8, new_score=0.78, threshold=0.05)

    assert abs(result["delta"] - (-0.02)) < 1e-9
    assert result["is_regression"] is False


def test_detect_regression_exactly_at_threshold():
    # Exactly at threshold should NOT be regression
    result = detect_regression(baseline_score=0.8, new_score=0.75, threshold=0.05)

    assert abs(result["delta"] - (-0.05)) < 1e-9
    assert result["is_regression"] is False


def test_detect_regression_just_below_threshold():
    # Just below threshold SHOULD be regression
    result = detect_regression(baseline_score=0.8, new_score=0.749, threshold=0.05)

    assert result["is_regression"] is True


def test_detect_regression_default_threshold():
    result = detect_regression(baseline_score=0.8, new_score=0.7)

    # Default threshold is 0.05
    assert result["threshold"] == 0.05
    assert result["is_regression"] is True  # -0.1 > 0.05


def test_detect_regression_validation():
    # Test invalid baseline_score
    try:
        detect_regression(baseline_score=1.5, new_score=0.8)
        assert False, "Should raise ValueError"
    except ValueError as e:
        assert "baseline_score" in str(e)

    # Test invalid new_score
    try:
        detect_regression(baseline_score=0.8, new_score=-0.1)
        assert False, "Should raise ValueError"
    except ValueError as e:
        assert "new_score" in str(e)

    # Test invalid threshold
    try:
        detect_regression(baseline_score=0.8, new_score=0.7, threshold=-0.1)
        assert False, "Should raise ValueError"
    except ValueError as e:
        assert "threshold" in str(e)


def test_should_fail_ci():
    # Regression detected
    result = detect_regression(baseline_score=0.9, new_score=0.6, threshold=0.1)
    assert should_fail_ci(result) is True

    # No regression
    result = detect_regression(baseline_score=0.8, new_score=0.85, threshold=0.05)
    assert should_fail_ci(result) is False


if __name__ == "__main__":
    test_detect_regression_clear_regression()
    test_detect_regression_no_regression()
    test_detect_regression_within_threshold()
    test_detect_regression_exactly_at_threshold()
    test_detect_regression_just_below_threshold()
    test_detect_regression_default_threshold()
    test_detect_regression_validation()
    test_should_fail_ci()
    print("All regression tests passed!")

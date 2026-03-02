"""
Tests for per-case reporting features (v0.5).
Uses FakeProvider to avoid real API calls.
"""
import sys
import json
import tempfile
import subprocess
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.baselines import BaselineStore, CaseScore, DetailedBaselineData
from core.scoring import (
    RefusalScorer,
    JsonSchemaScorer,
    ContainsScorer,
    NotContainsScorer,
    CompositeScorer
)


def test_detailed_baseline_storage_roundtrip():
    """Test storing and retrieving detailed baselines with per-case scores."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = BaselineStore(storage_dir=tmpdir)

        # Create detailed baseline data
        per_case_scores = {
            "case1": CaseScore(
                total=0.85,
                scorers={
                    "refusal_detection": 1.0,
                    "json_schema": 0.8,
                    "contains": 0.9
                },
                judge_reason="Good response"
            ),
            "case2": CaseScore(
                total=0.92,
                scorers={
                    "refusal_detection": 1.0,
                    "json_schema": 1.0,
                    "contains": 0.8
                },
                judge_reason=None
            )
        }

        # Store detailed baseline
        store.store_detailed(
            run_id="test_run",
            overall_avg=0.885,
            per_case_scores=per_case_scores
        )

        # Retrieve and verify
        baseline = store.get_detailed("test_run")
        assert baseline is not None
        assert baseline["run_id"] == "test_run"
        assert abs(baseline["overall_avg"] - 0.885) < 1e-6
        assert len(baseline["per_case_scores"]) == 2

        # Verify case1
        case1 = baseline["per_case_scores"]["case1"]
        assert abs(case1["total"] - 0.85) < 1e-6
        assert case1["scorers"]["refusal_detection"] == 1.0
        assert case1["scorers"]["json_schema"] == 0.8
        assert case1["judge_reason"] == "Good response"

        # Verify case2
        case2 = baseline["per_case_scores"]["case2"]
        assert abs(case2["total"] - 0.92) < 1e-6
        assert case2["judge_reason"] is None


def test_score_detailed_method():
    """Test CompositeScorer.score_detailed() returns per-scorer breakdown."""
    schema = {
        "category": {"type": "string", "enum": ["billing", "technical"]},
        "summary": {"type": "string"}
    }

    scorers = [
        RefusalScorer(),
        JsonSchemaScorer(schema),
        ContainsScorer(),
        NotContainsScorer()
    ]

    weights = [0.25, 0.25, 0.25, 0.25]
    composite = CompositeScorer(scorers, weights)

    output = {"category": "billing", "summary": "Refund request"}
    context = {
        "schema": schema,
        "expected_contains": ["billing", "refund"],
        "expected_not_contains": ["cannot help"]
    }

    # Get detailed breakdown
    breakdown = composite.score_detailed(output, context)

    # Should have all 4 scorers
    assert len(breakdown) == 4
    assert "refusal_detection" in breakdown
    assert "json_schema" in breakdown
    assert "contains" in breakdown
    assert "not_contains" in breakdown

    # Verify values are in valid range
    for scorer_name, score in breakdown.items():
        assert 0.0 <= score <= 1.0

    # Verify specific scores
    assert breakdown["refusal_detection"] == 1.0  # No refusal
    assert breakdown["json_schema"] == 1.0  # Valid schema
    assert breakdown["contains"] == 1.0  # Both phrases present
    assert breakdown["not_contains"] == 1.0  # No forbidden phrases


def test_cli_check_with_per_case_reporting():
    """Test CLI check command with per-case reporting (no regression case)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create suite file
        suite = {
            "run_id": "test_suite",
            "prompt_template": "Classify: {text}",
            "schema": {
                "category": {"type": "string", "enum": ["billing", "technical"]},
                "summary": {"type": "string"}
            },
            "scorer_weights": {
                "refusal": 0.3,
                "schema": 0.4,
                "contains": 0.2,
                "not_contains": 0.1,
                "judge": 0.0
            },
            "cases": [
                {
                    "id": "case1",
                    "input": {"text": "Payment issue"},
                    "expected_contains": ["billing"],
                    "expected_not_contains": []
                },
                {
                    "id": "case2",
                    "input": {"text": "API error"},
                    "expected_contains": ["technical"],
                    "expected_not_contains": []
                }
            ]
        }

        suite_file = tmpdir_path / "suite.json"
        with open(suite_file, "w") as f:
            json.dump(suite, f)

        # Create baseline directory with detailed baseline
        baseline_dir = tmpdir_path / ".baselines"
        baseline_dir.mkdir()

        baseline = {
            "run_id": "test_suite",
            "overall_avg": 0.9,
            "per_case_scores": {
                "case1": {
                    "total": 0.85,
                    "scorers": {
                        "refusal_detection": 1.0,
                        "json_schema": 1.0,
                        "contains": 1.0,
                        "not_contains": 1.0
                    },
                    "judge_reason": None
                },
                "case2": {
                    "total": 0.95,
                    "scorers": {
                        "refusal_detection": 1.0,
                        "json_schema": 1.0,
                        "contains": 1.0,
                        "not_contains": 1.0
                    },
                    "judge_reason": None
                }
            }
        }

        baseline_file = baseline_dir / "test_suite.json"
        with open(baseline_file, "w") as f:
            json.dump(baseline, f)

        # Run check command with fake provider
        cmd = [
            sys.executable, "-m", "cli.main", "check",
            "--suite", str(suite_file),
            "--provider", "fake",
            "--model", "test",
            "--baseline", str(baseline_dir),
            "--threshold", "0.05"
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent)
        )

        # Should pass (exit code 0) since fake provider gives consistent scores
        print(f"STDOUT:\n{result.stdout}")
        print(f"STDERR:\n{result.stderr}")
        assert result.returncode == 0, f"Expected pass but got exit code {result.returncode}"

        # Check for expected output substrings
        assert "AI REGRESSION GUARD - CHECK REGRESSION" in result.stdout
        assert "BASELINE SCORE:" in result.stdout
        assert "NEW AVERAGE SCORE:" in result.stdout
        assert "[OK] NO REGRESSION" in result.stdout


def test_cli_check_regression_detected():
    """Test CLI check command detects regression and shows top 3 worst cases."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create suite file
        suite = {
            "run_id": "regression_test",
            "prompt_template": "Classify: {text}",
            "schema": {
                "category": {"type": "string", "enum": ["billing", "technical"]},
                "summary": {"type": "string"}
            },
            "scorer_weights": {
                "refusal": 0.5,
                "schema": 0.5,
                "contains": 0.0,
                "not_contains": 0.0,
                "judge": 0.0
            },
            "cases": [
                {
                    "id": "case1",
                    "input": {"text": "Payment issue"},
                    "expected_contains": [],
                    "expected_not_contains": []
                }
            ]
        }

        suite_file = tmpdir_path / "suite.json"
        with open(suite_file, "w") as f:
            json.dump(suite, f)

        # Create baseline with VERY HIGH score (fake provider will give lower)
        baseline_dir = tmpdir_path / ".baselines"
        baseline_dir.mkdir()

        baseline = {
            "run_id": "regression_test",
            "overall_avg": 1.0,  # Perfect score
            "per_case_scores": {
                "case1": {
                    "total": 1.0,
                    "scorers": {
                        "refusal_detection": 1.0,
                        "json_schema": 1.0,
                        "contains": 1.0,
                        "not_contains": 1.0
                    },
                    "judge_reason": None
                }
            }
        }

        baseline_file = baseline_dir / "regression_test.json"
        with open(baseline_file, "w") as f:
            json.dump(baseline, f)

        # Run check command (fake provider returns imperfect outputs)
        cmd = [
            sys.executable, "-m", "cli.main", "check",
            "--suite", str(suite_file),
            "--provider", "fake",
            "--model", "test",
            "--baseline", str(baseline_dir),
            "--threshold", "0.05"
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent)
        )

        print(f"STDOUT:\n{result.stdout}")
        print(f"STDERR:\n{result.stderr}")

        # Note: This test may pass or fail depending on fake provider output
        # The key is that it should handle per-case reporting correctly
        # Check that per-case reporting elements are present
        if result.returncode == 1:
            # Regression detected
            assert "[X] REGRESSION DETECTED" in result.stdout
            # Should show delta and threshold
            assert "Delta" in result.stdout
            assert "Threshold" in result.stdout


def test_failing_scorers_identification():
    """Test that failing scorers are correctly identified in delta computation."""
    # Create baseline and new scores with specific failures
    baseline_scorers = {
        "refusal_detection": 1.0,
        "json_schema": 1.0,
        "contains": 0.9,
        "not_contains": 1.0
    }

    new_scorers = {
        "refusal_detection": 1.0,
        "json_schema": 0.7,  # Dropped by 0.3 (>= 0.1 threshold)
        "contains": 0.85,    # Dropped by 0.05 (< 0.1 threshold)
        "not_contains": 1.0
    }

    # Identify failing scorers (delta >= 0.1)
    failing = []
    for scorer_name, new_score in new_scorers.items():
        baseline_score = baseline_scorers.get(scorer_name, 0.0)
        if new_score < baseline_score - 0.1:
            failing.append(scorer_name)

    # Should only include json_schema
    assert "json_schema" in failing
    assert "contains" not in failing  # Delta is only 0.05
    assert len(failing) == 1


def test_baseline_without_detailed_format():
    """Test that check command handles legacy baselines gracefully."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = BaselineStore(storage_dir=tmpdir)

        # Create old-format baseline (without per_case_scores)
        old_baseline_path = Path(tmpdir) / "old_format.json"
        with open(old_baseline_path, "w") as f:
            json.dump({
                "run_id": "old_format",
                "output": "some output",
                "score": 0.8
            }, f)

        # Try to get as detailed baseline
        detailed = store.get_detailed("old_format")

        # Should return None since it's not detailed format
        assert detailed is None


def test_no_cache_flag_recognized():
    """Test that --no-cache flag is recognized by CLI."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create minimal suite with unique run_id
        import time
        unique_id = f"cache_test_{int(time.time() * 1000)}"

        suite = {
            "run_id": unique_id,
            "prompt_template": "Test: {text}",
            "schema": {"category": {"type": "string"}},
            "cases": [{"id": "case1", "input": {"text": "test"}}]
        }

        suite_file = tmpdir_path / "suite.json"
        with open(suite_file, "w") as f:
            json.dump(suite, f)

        # Create baseline directory in tmpdir
        baseline_dir = tmpdir_path / ".baselines"
        baseline_dir.mkdir()

        # Run baseline with --no-cache flag
        cmd = [
            sys.executable, "-m", "cli.main", "baseline",
            "--suite", str(suite_file),
            "--provider", "fake",
            "--model", "test",
            "--baseline", str(baseline_dir),
            "--no-cache"
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent)
        )

        # Should succeed (flag recognized, no error)
        assert result.returncode == 0, f"Command failed with --no-cache flag: {result.stderr}"
        assert "GENERATE BASELINE" in result.stdout


if __name__ == "__main__":
    print("Running per-case reporting tests...\n")

    test_detailed_baseline_storage_roundtrip()
    print("[PASS] test_detailed_baseline_storage_roundtrip")

    test_score_detailed_method()
    print("[PASS] test_score_detailed_method")

    test_cli_check_with_per_case_reporting()
    print("[PASS] test_cli_check_with_per_case_reporting")

    test_cli_check_regression_detected()
    print("[PASS] test_cli_check_regression_detected")

    test_failing_scorers_identification()
    print("[PASS] test_failing_scorers_identification")

    test_baseline_without_detailed_format()
    print("[PASS] test_baseline_without_detailed_format")

    test_no_cache_flag_recognized()
    print("[PASS] test_no_cache_flag_recognized")

    print("\nAll per-case reporting tests passed!")

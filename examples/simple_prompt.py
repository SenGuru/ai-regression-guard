"""
Simple example: Support ticket classifier regression detection.

This demonstrates the core regression detection flow:
1. Score a baseline output
2. Score a new output
3. Detect if quality regressed
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.scoring import RefusalScorer, JsonSchemaScorer, CompositeScorer
from core.regressions import detect_regression


def main():
    print("=" * 60)
    print("AI REGRESSION DETECTION - SUPPORT TICKET CLASSIFIER")
    print("=" * 60)
    print()

    # Define expected schema
    schema = {
        "category": {"type": "string", "enum": ["billing", "technical", "account", "other"]},
        "priority": {"type": "string", "enum": ["low", "medium", "high"]},
        "summary": {"type": "string"},
    }

    # Create scorer
    scorer = CompositeScorer(
        [RefusalScorer(), JsonSchemaScorer(schema)],
        weights=[0.3, 0.7]  # Weight schema adherence more heavily
    )

    # Baseline output (good)
    baseline_output = {
        "category": "billing",
        "priority": "high",
        "summary": "Customer unable to process payment"
    }

    # New output (regressed - missing priority field)
    new_output = {
        "category": "billing",
        "summary": "Payment issue"
    }

    print("BASELINE OUTPUT:")
    print(f"  {baseline_output}")
    print()

    baseline_score = scorer.score(baseline_output)
    print(f"BASELINE SCORE: {baseline_score:.2f}")
    print()

    print("NEW OUTPUT:")
    print(f"  {new_output}")
    print()

    new_score = scorer.score(new_output)
    print(f"NEW VERSION SCORE: {new_score:.2f}")
    print()

    # Detect regression
    result = detect_regression(
        baseline_score=baseline_score,
        new_score=new_score,
        threshold=0.1
    )

    print("-" * 60)
    print(f"DELTA: {result['delta']:+.2f}")
    print(f"THRESHOLD: {result['threshold']:.2f}")
    print()

    if result["is_regression"]:
        print("[X] REGRESSION DETECTED")
        print()
        print("Quality degraded - this would FAIL CI")
        return 1
    else:
        print("[OK] NO REGRESSION")
        print()
        print("Quality maintained or improved - this would PASS CI")
        return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)

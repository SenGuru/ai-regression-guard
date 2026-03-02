"""
CLI for AI Regression Guard.
"""
import argparse
import json
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.scoring import (
    RefusalScorer,
    JsonSchemaScorer,
    CompositeScorer,
    ContainsScorer,
    NotContainsScorer,
    LLMJudgeScorer,
)
from core.regressions import detect_regression
from core.baselines import BaselineStore, CaseScore
from providers import get_provider


def load_cases_file(cases_path: str) -> dict:
    """Load test cases from JSON file."""
    with open(cases_path, 'r') as f:
        return json.load(f)


def run_command(args):
    """
    Run regression detection on test cases.

    Returns exit code: 0 for pass, 1 for regression detected
    """
    print("=" * 70)
    print("AI REGRESSION GUARD - CI CHECK")
    print("=" * 70)
    print()

    # Load cases file
    try:
        cases = load_cases_file(args.cases)
    except FileNotFoundError:
        print(f"[ERROR] Cases file not found: {args.cases}")
        return 1
    except json.JSONDecodeError as e:
        print(f"[ERROR] Invalid JSON in cases file: {e}")
        return 1

    run_id = cases.get("run_id", args.run_id)
    schema = cases.get("schema", {})
    outputs = cases.get("outputs", [])
    scorer_weights = cases.get("scorer_weights", {"refusal": 0.3, "schema": 0.7})

    if not outputs:
        print("[ERROR] No outputs found in cases file")
        return 1

    print(f"RUN ID: {run_id}")
    print(f"TEST CASES: {len(outputs)}")
    print(f"THRESHOLD: {args.threshold}")
    print()

    # Create scorer
    scorer = CompositeScorer(
        [RefusalScorer(), JsonSchemaScorer(schema)],
        weights=[scorer_weights["refusal"], scorer_weights["schema"]]
    )

    # Score all outputs
    print("Scoring outputs...")
    scores = []
    for i, output in enumerate(outputs, 1):
        score = scorer.score(output)
        scores.append(score)
        print(f"  Case {i}: {score:.2f}")

    # Average score
    avg_score = sum(scores) / len(scores)
    print()
    print(f"AVERAGE SCORE: {avg_score:.2f}")
    print()

    # Load baseline
    store = BaselineStore(storage_dir=args.baseline)
    baseline = store.get(run_id)

    if baseline is None:
        print("[WARNING] No baseline found - storing current results as baseline")
        print()
        # Store first output as representative
        store.store(run_id, outputs[0] if outputs else {}, avg_score)
        print(f"Baseline saved: {avg_score:.2f}")
        print()
        print("[OK] BASELINE CREATED - CI PASS")
        return 0

    baseline_score = baseline["score"]
    print(f"BASELINE SCORE: {baseline_score:.2f}")
    print()

    # Detect regression
    result = detect_regression(
        baseline_score=baseline_score,
        new_score=avg_score,
        threshold=args.threshold
    )

    # Print results table
    print("-" * 70)
    print(f"{'Metric':<30} {'Value':>10}")
    print("-" * 70)
    print(f"{'Baseline Score':<30} {baseline_score:>10.2f}")
    print(f"{'New Average Score':<30} {avg_score:>10.2f}")
    print(f"{'Delta':<30} {result['delta']:>+10.2f}")
    print(f"{'Threshold':<30} {args.threshold:>10.2f}")
    print("-" * 70)
    print()

    if result["is_regression"]:
        print("[X] REGRESSION DETECTED")
        print()
        print("Quality degraded beyond threshold - FAILING CI")
        return 1
    else:
        print("[OK] NO REGRESSION")
        print()
        print("Quality maintained or improved - PASSING CI")
        return 0


def load_suite_file(suite_path: str) -> dict:
    """Load test suite from JSON file."""
    with open(suite_path, 'r') as f:
        return json.load(f)


def build_prompt(template: str, input_data: dict) -> str:
    """Build prompt from template and input data."""
    return template.format(**input_data)


def baseline_command(args):
    """
    Generate baseline using LLM provider.

    Returns exit code: 0 for success, 1 for error
    """
    print("=" * 70)
    print("AI REGRESSION GUARD - GENERATE BASELINE")
    print("=" * 70)
    print()

    # Load suite file
    try:
        suite = load_suite_file(args.suite)
    except FileNotFoundError:
        print(f"[ERROR] Suite file not found: {args.suite}")
        return 1
    except json.JSONDecodeError as e:
        print(f"[ERROR] Invalid JSON in suite file: {e}")
        return 1

    run_id = suite.get("run_id")
    if not run_id:
        print("[ERROR] Suite file must contain 'run_id'")
        return 1

    schema = suite.get("schema", {})
    cases = suite.get("cases", [])
    scorer_weights = suite.get("scorer_weights", {
        "refusal": 0.3,
        "schema": 0.7,
        "contains": 0.0,
        "not_contains": 0.0,
        "judge": 0.0
    })
    prompt_template = suite.get("prompt_template")
    default_rubric = suite.get("default_rubric", "")

    if not cases:
        print("[ERROR] No cases found in suite file")
        return 1

    if not prompt_template:
        print("[ERROR] Suite file must contain 'prompt_template'")
        return 1

    print(f"RUN ID: {run_id}")
    print(f"PROVIDER: {args.provider}")
    print(f"MODEL: {args.model}")
    print(f"TEST CASES: {len(cases)}")
    print()

    # Initialize provider
    try:
        provider = get_provider(args.provider, args.model)
    except Exception as e:
        print(f"[ERROR] Failed to initialize provider: {e}")
        return 1

    # Build scorers list
    scorers = [
        RefusalScorer(),
        JsonSchemaScorer(schema),
        ContainsScorer(),
        NotContainsScorer(),
    ]
    weights = [
        scorer_weights.get("refusal", 0.0),
        scorer_weights.get("schema", 0.0),
        scorer_weights.get("contains", 0.0),
        scorer_weights.get("not_contains", 0.0),
    ]

    # Add judge scorer if enabled
    judge_weight = scorer_weights.get("judge", 0.0)
    judge_scorer = None
    if judge_weight > 0:
        # Initialize judge provider (use same provider for now, could be different)
        judge_scorer = LLMJudgeScorer(
            judge_provider=provider,
            run_id=run_id,
            cache_dir=getattr(args, 'judge_cache_dir', '.judge_cache'),
            enable_cache=not getattr(args, 'no_cache', False)
        )
        scorers.append(judge_scorer)
        weights.append(judge_weight)

    # Normalize weights to sum to 1
    total_weight = sum(weights)
    if total_weight > 0:
        weights = [w / total_weight for w in weights]
    else:
        # If all weights are 0, use equal weights
        weights = [1.0 / len(scorers)] * len(scorers)

    # Create composite scorer
    scorer = CompositeScorer(scorers, weights)

    # Generate outputs and score them
    print("Generating outputs...")
    per_case_scores = {}

    for i, case in enumerate(cases, 1):
        case_id = case.get("id", f"case_{i}")
        input_data = case.get("input", {})
        expected_contains = case.get("expected_contains", [])
        expected_not_contains = case.get("expected_not_contains", [])
        case_rubric = case.get("rubric")
        if case_rubric is None:
            case_rubric = default_rubric

        # Build prompt
        try:
            prompt = build_prompt(prompt_template, input_data)
        except KeyError as e:
            print(f"  [ERROR] Case {case_id}: Missing input field {e}")
            return 1

        # Generate output
        try:
            print(f"  {case_id}: Generating...", end=" ", flush=True)
            output_text = provider.generate(prompt)
            print(f"Done", end=" ")

            # Parse JSON output
            try:
                output = json.loads(output_text)
            except json.JSONDecodeError:
                output = output_text

            # Build context for scoring
            context = {
                "case_id": case_id,
                "schema": schema,
                "expected_contains": expected_contains,
                "expected_not_contains": expected_not_contains,
                "rubric": case_rubric,
                "input": input_data
            }

            # Get detailed scores
            scorer_breakdown = scorer.score_detailed(output, context)
            total_score = scorer.score(output, context)

            # Get judge reason if available
            judge_reason = None
            if judge_scorer:
                judge_reason = judge_scorer.get_last_reason()

            # Store per-case score
            per_case_scores[case_id] = CaseScore(
                total=total_score,
                scorers=scorer_breakdown,
                judge_reason=judge_reason
            )

            print(f"| Score: {total_score:.2f}")

        except Exception as e:
            print(f"[ERROR] Failed: {e}")
            return 1

    # Calculate average score
    total_scores = [cs["total"] for cs in per_case_scores.values()]
    avg_score = sum(total_scores) / len(total_scores) if total_scores else 0.0
    print()
    print(f"OVERALL AVERAGE: {avg_score:.2f}")
    print()

    # Print per-case table
    print("Per-case scores:")
    print(f"{'Case ID':<30} {'Score':>8} {'Judge Reason':<40}")
    print("-" * 80)
    for case_id, case_score in per_case_scores.items():
        judge_reason = case_score.get("judge_reason") or ""
        if judge_reason and len(judge_reason) > 40:
            judge_reason = judge_reason[:37] + "..."
        print(f"{case_id:<30} {case_score['total']:>8.2f} {judge_reason:<40}")
    print()

    # Store baseline
    store = BaselineStore(storage_dir=args.baseline)

    # Check if baseline already exists
    if store.exists(run_id):
        print(f"[WARNING] Baseline '{run_id}' already exists")
        response = input("Overwrite? (y/N): ").strip().lower()
        if response != 'y':
            print("Aborted")
            return 1

    # Store detailed baseline
    store.store_detailed(run_id, avg_score, per_case_scores)

    print(f"[OK] Baseline saved: {avg_score:.2f}")
    print(f"Storage: {args.baseline}/{run_id}.json")

    return 0


def check_command(args):
    """
    Check for regression by generating new outputs and comparing to baseline.

    Returns exit code: 0 for pass, 1 for regression or error
    """
    print("=" * 70)
    print("AI REGRESSION GUARD - CHECK REGRESSION")
    print("=" * 70)
    print()

    # Load suite file
    try:
        suite = load_suite_file(args.suite)
    except FileNotFoundError:
        print(f"[ERROR] Suite file not found: {args.suite}")
        return 1
    except json.JSONDecodeError as e:
        print(f"[ERROR] Invalid JSON in suite file: {e}")
        return 1

    run_id = suite.get("run_id")
    if not run_id:
        print("[ERROR] Suite file must contain 'run_id'")
        return 1

    schema = suite.get("schema", {})
    cases = suite.get("cases", [])
    scorer_weights = suite.get("scorer_weights", {
        "refusal": 0.2,
        "schema": 0.3,
        "contains": 0.2,
        "not_contains": 0.1,
        "judge": 0.2
    })
    prompt_template = suite.get("prompt_template")
    default_rubric = suite.get("rubric")

    if not cases:
        print("[ERROR] No cases found in suite file")
        return 1

    if not prompt_template:
        print("[ERROR] Suite file must contain 'prompt_template'")
        return 1

    print(f"RUN ID: {run_id}")
    print(f"PROVIDER: {args.provider}")
    print(f"MODEL: {args.model}")
    print(f"TEST CASES: {len(cases)}")
    print(f"THRESHOLD: {args.threshold}")
    print()

    # Load detailed baseline
    store = BaselineStore(storage_dir=args.baseline)
    baseline = store.get_detailed(run_id)

    if baseline is None:
        print(f"[ERROR] No detailed baseline found for '{run_id}'")
        print(f"Run 'ai-regression-guard baseline' first to create a baseline")
        return 1

    baseline_avg = baseline["overall_avg"]
    baseline_per_case = baseline["per_case_scores"]
    print(f"BASELINE SCORE: {baseline_avg:.2f}")
    print()

    # Initialize provider
    try:
        provider = get_provider(args.provider, args.model)
    except Exception as e:
        print(f"[ERROR] Failed to initialize provider: {e}")
        return 1

    # Build scorers list
    scorers = [
        RefusalScorer(),
        JsonSchemaScorer(schema),
        ContainsScorer(),
        NotContainsScorer(),
    ]
    weights = [
        scorer_weights.get("refusal", 0.0),
        scorer_weights.get("schema", 0.0),
        scorer_weights.get("contains", 0.0),
        scorer_weights.get("not_contains", 0.0),
    ]

    # Add judge scorer if enabled
    judge_weight = scorer_weights.get("judge", 0.0)
    judge_scorer = None
    if judge_weight > 0:
        judge_scorer = LLMJudgeScorer(
            judge_provider=provider,
            run_id=run_id,
            cache_dir=getattr(args, 'judge_cache_dir', '.judge_cache'),
            enable_cache=not getattr(args, 'no_cache', False)
        )
        scorers.append(judge_scorer)
        weights.append(judge_weight)

    # Normalize weights to sum to 1
    total_weight = sum(weights)
    if total_weight > 0:
        weights = [w / total_weight for w in weights]
    else:
        weights = [1.0 / len(scorers)] * len(scorers)

    # Create composite scorer
    scorer = CompositeScorer(scorers, weights)

    # Generate outputs and score them
    print("Generating outputs...")
    new_per_case_scores: dict[str, CaseScore] = {}

    for i, case in enumerate(cases, 1):
        case_id = case.get("id", f"case_{i}")
        input_data = case.get("input", {})
        expected_contains = case.get("expected_contains", [])
        expected_not_contains = case.get("expected_not_contains", [])
        case_rubric = case.get("rubric")
        if case_rubric is None:
            case_rubric = default_rubric

        # Build prompt
        try:
            prompt = build_prompt(prompt_template, input_data)
        except KeyError as e:
            print(f"  [ERROR] Case {case_id}: Missing input field {e}")
            return 1

        # Generate output
        try:
            print(f"  {case_id}: Generating...", end=" ", flush=True)
            output_text = provider.generate(prompt)
            print(f"Done")

            # Parse JSON output
            try:
                output = json.loads(output_text)
            except json.JSONDecodeError:
                output = output_text

            # Build context for scoring
            context = {
                "case_id": case_id,
                "schema": schema,
                "expected_contains": expected_contains,
                "expected_not_contains": expected_not_contains,
                "rubric": case_rubric,
                "input": input_data
            }

            # Get detailed scores
            scorer_breakdown = scorer.score_detailed(output, context)
            total_score = scorer.score(output, context)

            # Get judge reason if available
            judge_reason = None
            if judge_scorer:
                judge_reason = judge_scorer.get_last_reason()

            # Store per-case score
            new_per_case_scores[case_id] = CaseScore(
                total=total_score,
                scorers=scorer_breakdown,
                judge_reason=judge_reason
            )

            print(f"    Score: {total_score:.2f}")

        except Exception as e:
            print(f"[ERROR] Failed: {e}")
            return 1

    # Calculate new overall average
    new_avg = sum(cs["total"] for cs in new_per_case_scores.values()) / len(new_per_case_scores)
    print()
    print(f"NEW AVERAGE SCORE: {new_avg:.2f}")
    print()

    # Compute per-case deltas
    case_deltas = []
    for case_id, new_score_data in new_per_case_scores.items():
        baseline_score_data = baseline_per_case.get(case_id)
        if baseline_score_data:
            delta = new_score_data["total"] - baseline_score_data["total"]

            # Find failing scorers (new < baseline by >= 0.1)
            failing_scorers = []
            for scorer_name, new_scorer_score in new_score_data["scorers"].items():
                baseline_scorer_score = baseline_score_data["scorers"].get(scorer_name)
                if baseline_scorer_score is None:
                    # Baseline missing this scorer - consider failing if new score is low
                    if new_scorer_score < 0.5:
                        failing_scorers.append(scorer_name)
                elif new_scorer_score < baseline_scorer_score - 0.1:
                    failing_scorers.append(scorer_name)

            case_deltas.append({
                "case_id": case_id,
                "baseline_total": baseline_score_data["total"],
                "new_total": new_score_data["total"],
                "delta": delta,
                "failing_scorers": failing_scorers,
                "judge_reason": new_score_data.get("judge_reason")
            })
        else:
            # New case not in baseline
            case_deltas.append({
                "case_id": case_id,
                "baseline_total": 0.0,
                "new_total": new_score_data["total"],
                "delta": new_score_data["total"],
                "failing_scorers": [],
                "judge_reason": new_score_data.get("judge_reason")
            })

    # Detect regression
    overall_delta = new_avg - baseline_avg
    is_regression = overall_delta < -args.threshold

    # Print results
    print("-" * 70)
    print(f"{'Metric':<30} {'Value':>10}")
    print("-" * 70)
    print(f"{'Baseline Average':<30} {baseline_avg:>10.2f}")
    print(f"{'New Average':<30} {new_avg:>10.2f}")
    print(f"{'Delta':<30} {overall_delta:>+10.2f}")
    print(f"{'Threshold':<30} {-args.threshold:>10.2f}")
    print("-" * 70)
    print()

    if is_regression:
        print("[X] REGRESSION DETECTED")
        print()

        # Sort cases by delta (most negative first)
        sorted_cases = sorted(case_deltas, key=lambda x: x["delta"])

        # Print top 3 worst cases
        print("TOP 3 WORST CASES:")
        print("-" * 70)
        for i, case_data in enumerate(sorted_cases[:3], 1):
            print(f"{i}. {case_data['case_id']}")
            print(f"   Baseline: {case_data['baseline_total']:.2f} | New: {case_data['new_total']:.2f} | Delta: {case_data['delta']:+.2f}")
            if case_data['failing_scorers']:
                print(f"   Failing scorers: {', '.join(case_data['failing_scorers'])}")
            if case_data['judge_reason']:
                print(f"   Judge: {case_data['judge_reason']}")
            print()

        # Print full per-case table
        print("FULL PER-CASE REPORT:")
        print("-" * 120)
        print(f"{'Case ID':<20} {'Baseline':>10} {'New':>10} {'Delta':>10} {'Failing Scorers':<30} {'Judge Reason':<30}")
        print("-" * 120)
        for case_data in sorted_cases:
            failing_str = ", ".join(case_data['failing_scorers']) if case_data['failing_scorers'] else "-"
            judge_str = (case_data['judge_reason'][:28] + "..") if case_data['judge_reason'] and len(case_data['judge_reason']) > 30 else (case_data['judge_reason'] or "-")
            print(f"{case_data['case_id']:<20} {case_data['baseline_total']:>10.2f} {case_data['new_total']:>10.2f} {case_data['delta']:>+10.2f} {failing_str:<30} {judge_str:<30}")
        print("-" * 120)
        print()

        print("Quality degraded beyond threshold - FAILING CI")
        return 1
    else:
        print("[OK] NO REGRESSION")
        print()
        print("Quality maintained or improved - PASSING CI")
        return 0


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="ai-regression-guard",
        description="AI Regression Detection for CI/CD"
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Run command
    run_parser = subparsers.add_parser("run", help="Run regression detection")
    run_parser.add_argument(
        "--run-id",
        type=str,
        help="Run identifier (can be specified in cases file)"
    )
    run_parser.add_argument(
        "--baseline",
        type=str,
        default=".baselines",
        help="Path to baseline storage directory (default: .baselines)"
    )
    run_parser.add_argument(
        "--cases",
        type=str,
        required=True,
        help="Path to test cases JSON file"
    )
    run_parser.add_argument(
        "--threshold",
        type=float,
        default=0.05,
        help="Regression threshold (default: 0.05)"
    )

    # Baseline command
    baseline_parser = subparsers.add_parser(
        "baseline",
        help="Generate baseline by running LLM on test suite"
    )
    baseline_parser.add_argument(
        "--suite",
        type=str,
        required=True,
        help="Path to test suite JSON file"
    )
    baseline_parser.add_argument(
        "--provider",
        type=str,
        required=True,
        choices=["openai", "anthropic", "fake"],
        help="LLM provider (openai, anthropic, fake)"
    )
    baseline_parser.add_argument(
        "--model",
        type=str,
        required=True,
        help="Model name (e.g., gpt-4, claude-3-5-sonnet-20241022)"
    )
    baseline_parser.add_argument(
        "--baseline",
        type=str,
        default=".baselines",
        help="Path to baseline storage directory (default: .baselines)"
    )
    baseline_parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable judge result caching (for debugging only, not recommended in CI)"
    )

    # Check command
    check_parser = subparsers.add_parser(
        "check",
        help="Check for regression by running LLM and comparing to baseline"
    )
    check_parser.add_argument(
        "--suite",
        type=str,
        required=True,
        help="Path to test suite JSON file"
    )
    check_parser.add_argument(
        "--provider",
        type=str,
        required=True,
        choices=["openai", "anthropic", "fake"],
        help="LLM provider (openai, anthropic, fake)"
    )
    check_parser.add_argument(
        "--model",
        type=str,
        required=True,
        help="Model name (e.g., gpt-4, claude-3-5-sonnet-20241022)"
    )
    check_parser.add_argument(
        "--baseline",
        type=str,
        default=".baselines",
        help="Path to baseline storage directory (default: .baselines)"
    )
    check_parser.add_argument(
        "--threshold",
        type=float,
        default=0.05,
        help="Regression threshold (default: 0.05)"
    )
    check_parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable judge result caching (for debugging only, not recommended in CI)"
    )

    args = parser.parse_args()

    if args.command == "run":
        exit_code = run_command(args)
        sys.exit(exit_code)
    elif args.command == "baseline":
        exit_code = baseline_command(args)
        sys.exit(exit_code)
    elif args.command == "check":
        exit_code = check_command(args)
        sys.exit(exit_code)
    else:
        parser.print_help()
        sys.exit(0)


if __name__ == "__main__":
    main()

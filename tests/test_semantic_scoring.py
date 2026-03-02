"""
Tests for semantic scoring (contains, not_contains, LLM judge).
"""
import json
import sys
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.scoring import ContainsScorer, NotContainsScorer, LLMJudgeScorer
from core.judge_cache import JudgeCache
from providers.fake import FakeJudgeProvider


def test_contains_scorer_all_present():
    """Test ContainsScorer when all expected phrases are present."""
    scorer = ContainsScorer()

    output = "This is about billing and payment issues with credit card"
    context = {"expected_contains": ["billing", "payment", "credit card"]}

    score = scorer.score(output, context)
    assert score == 1.0


def test_contains_scorer_partial():
    """Test ContainsScorer with partial matches."""
    scorer = ContainsScorer()

    output = "This is about billing issues"
    context = {"expected_contains": ["billing", "payment", "credit card"]}

    # Only 1 out of 3 present
    score = scorer.score(output, context)
    assert abs(score - (1.0 / 3.0)) < 1e-6


def test_contains_scorer_case_insensitive():
    """Test ContainsScorer is case-insensitive."""
    scorer = ContainsScorer()

    output = "This is about BILLING and PAYMENT"
    context = {"expected_contains": ["billing", "payment"]}

    score = scorer.score(output, context)
    assert score == 1.0


def test_contains_scorer_no_requirements():
    """Test ContainsScorer when no requirements specified."""
    scorer = ContainsScorer()

    output = "Anything"
    context = {}

    score = scorer.score(output, context)
    assert score == 1.0  # No requirements = pass


def test_not_contains_scorer_passes():
    """Test NotContainsScorer when no forbidden phrases present."""
    scorer = NotContainsScorer()

    output = "This is a helpful response"
    context = {"expected_not_contains": ["cannot help", "as an ai", "i don't know"]}

    score = scorer.score(output, context)
    assert score == 1.0


def test_not_contains_scorer_fails():
    """Test NotContainsScorer when forbidden phrase present."""
    scorer = NotContainsScorer()

    output = "Sorry, I cannot help with that"
    context = {"expected_not_contains": ["cannot help", "as an ai"]}

    score = scorer.score(output, context)
    assert score == 0.0


def test_not_contains_scorer_case_insensitive():
    """Test NotContainsScorer is case-insensitive."""
    scorer = NotContainsScorer()

    output = "AS AN AI, I cannot help"
    context = {"expected_not_contains": ["as an ai"]}

    score = scorer.score(output, context)
    assert score == 0.0


def test_llm_judge_scorer_basic():
    """Test LLMJudgeScorer basic functionality."""
    judge_provider = FakeJudgeProvider(default_score=0.85, default_reason="good quality")

    tmpdir = tempfile.mkdtemp()
    try:
        scorer = LLMJudgeScorer(
            judge_provider=judge_provider,
            run_id="test_run",
            cache_dir=tmpdir,
            enable_cache=False  # Disable cache for this test
        )

        output = {"category": "billing", "summary": "Payment issue"}
        context = {
            "case_id": "test_case",
            "rubric": "Must classify correctly",
            "input": {"text": "Customer payment problem"}
        }

        score = scorer.score(output, context)
        assert abs(score - 0.85) < 1e-6
        assert judge_provider.call_count == 1

    finally:
        shutil.rmtree(tmpdir)


def test_llm_judge_scorer_caching():
    """Test that LLMJudgeScorer caches results."""
    judge_provider = FakeJudgeProvider(default_score=0.9)

    tmpdir = tempfile.mkdtemp()
    try:
        scorer = LLMJudgeScorer(
            judge_provider=judge_provider,
            run_id="test_run",
            cache_dir=tmpdir,
            enable_cache=True
        )

        output = {"category": "billing"}
        context = {
            "case_id": "test_case",
            "rubric": "Test rubric",
            "input": {"text": "Test input"}
        }

        # First call - should hit provider
        score1 = scorer.score(output, context)
        assert judge_provider.call_count == 1

        # Second call with same inputs - should use cache
        score2 = scorer.score(output, context)
        assert judge_provider.call_count == 1  # No additional call
        assert score1 == score2

    finally:
        shutil.rmtree(tmpdir)


def test_llm_judge_scorer_no_rubric():
    """Test that LLMJudgeScorer skips when no rubric provided."""
    judge_provider = FakeJudgeProvider()

    tmpdir = tempfile.mkdtemp()
    try:
        scorer = LLMJudgeScorer(
            judge_provider=judge_provider,
            run_id="test_run",
            cache_dir=tmpdir
        )

        output = {"category": "billing"}
        context = {
            "case_id": "test_case",
            "rubric": "",  # Empty rubric
            "input": {"text": "Test"}
        }

        score = scorer.score(output, context)
        assert score == 1.0  # No rubric = skip judge = full score
        assert judge_provider.call_count == 0

    finally:
        shutil.rmtree(tmpdir)


def test_llm_judge_scorer_parse_error_safety():
    """Test that LLMJudgeScorer handles parse errors safely."""
    # Create a provider that returns invalid JSON
    class BadProvider:
        name = "bad/provider"
        def generate(self, prompt):
            return "This is not JSON!"

    tmpdir = tempfile.mkdtemp()
    try:
        scorer = LLMJudgeScorer(
            judge_provider=BadProvider(),
            run_id="test_run",
            cache_dir=tmpdir,
            enable_cache=False
        )

        output = {"category": "billing"}
        context = {
            "case_id": "test_case",
            "rubric": "Test rubric",
            "input": {"text": "Test"}
        }

        # Should not crash, should return 0.0
        score = scorer.score(output, context)
        assert score == 0.0

    finally:
        shutil.rmtree(tmpdir)


def test_judge_cache_basic():
    """Test JudgeCache basic get/set."""
    tmpdir = tempfile.mkdtemp()
    try:
        cache = JudgeCache(cache_dir=tmpdir)

        # Set a result
        cache.set(
            run_id="test_run",
            case_id="case1",
            output_text="test output",
            rubric="test rubric",
            judge_provider="fake",
            judge_model="test",
            score=0.85,
            reason="good"
        )

        # Get it back
        result = cache.get(
            run_id="test_run",
            case_id="case1",
            output_text="test output",
            rubric="test rubric",
            judge_provider="fake",
            judge_model="test"
        )

        assert result is not None
        assert result["score"] == 0.85
        assert result["reason"] == "good"

    finally:
        shutil.rmtree(tmpdir)


def test_judge_cache_miss():
    """Test JudgeCache returns None on cache miss."""
    tmpdir = tempfile.mkdtemp()
    try:
        cache = JudgeCache(cache_dir=tmpdir)

        result = cache.get(
            run_id="test_run",
            case_id="nonexistent",
            output_text="test",
            rubric="test",
            judge_provider="fake",
            judge_model="test"
        )

        assert result is None

    finally:
        shutil.rmtree(tmpdir)


if __name__ == "__main__":
    test_contains_scorer_all_present()
    test_contains_scorer_partial()
    test_contains_scorer_case_insensitive()
    test_contains_scorer_no_requirements()
    test_not_contains_scorer_passes()
    test_not_contains_scorer_fails()
    test_not_contains_scorer_case_insensitive()
    test_llm_judge_scorer_basic()
    test_llm_judge_scorer_caching()
    test_llm_judge_scorer_no_rubric()
    test_llm_judge_scorer_parse_error_safety()
    test_judge_cache_basic()
    test_judge_cache_miss()
    print("All semantic scoring tests passed!")

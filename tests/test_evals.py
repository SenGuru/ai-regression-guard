"""
Tests for core scoring logic.
"""
import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.scoring import RefusalScorer, JsonSchemaScorer, CompositeScorer
from core.baselines import BaselineStore
import tempfile
import shutil


def test_refusal_scorer_detects_refusals():
    scorer = RefusalScorer()

    # Should detect refusals
    assert scorer.score("I cannot help with that") == 0.0
    assert scorer.score("Sorry, I can't do that") == 0.0
    assert scorer.score("As an AI, I'm not able to assist") == 0.0

    # Should not flag normal responses
    assert scorer.score("Here is your answer") == 1.0
    assert scorer.score('{"result": "success"}') == 1.0


def test_refusal_scorer_with_dict():
    scorer = RefusalScorer()

    # Should detect refusals in dict (converted to JSON)
    assert scorer.score({"message": "I cannot help"}) == 0.0
    assert scorer.score({"result": "ok"}) == 1.0


def test_json_schema_scorer_valid():
    schema = {
        "category": {"type": "string", "enum": ["billing", "technical"]},
        "priority": {"type": "string", "enum": ["low", "high"]},
        "summary": {"type": "string"},
    }
    scorer = JsonSchemaScorer(schema)

    # Perfect match
    output = {"category": "billing", "priority": "high", "summary": "Payment issue"}
    assert scorer.score(output) == 1.0


def test_json_schema_scorer_partial():
    schema = {
        "category": {"type": "string", "enum": ["billing", "technical"]},
        "priority": {"type": "string", "enum": ["low", "high"]},
        "summary": {"type": "string"},
    }
    scorer = JsonSchemaScorer(schema)

    # Missing one field
    output = {"category": "billing", "priority": "high"}
    assert scorer.score(output) == 2.0 / 3.0

    # Only one field correct
    output = {"category": "billing"}
    assert scorer.score(output) == 1.0 / 3.0


def test_json_schema_scorer_invalid_enum():
    schema = {
        "category": {"type": "string", "enum": ["billing", "technical"]},
    }
    scorer = JsonSchemaScorer(schema)

    # Invalid enum value
    output = {"category": "wrong"}
    assert scorer.score(output) == 0.0


def test_json_schema_scorer_empty_string():
    schema = {
        "summary": {"type": "string"},
    }
    scorer = JsonSchemaScorer(schema)

    # Empty string should fail
    output = {"summary": ""}
    assert scorer.score(output) == 0.0

    # Whitespace should fail
    output = {"summary": "   "}
    assert scorer.score(output) == 0.0


def test_json_schema_scorer_with_string_input():
    schema = {
        "category": {"type": "string", "enum": ["billing"]},
    }
    scorer = JsonSchemaScorer(schema)

    # Valid JSON string
    output_str = '{"category": "billing"}'
    assert scorer.score(output_str) == 1.0

    # Invalid JSON
    output_str = "not json"
    assert scorer.score(output_str) == 0.0


def test_composite_scorer_equal_weights():
    schema = {"category": {"type": "string", "enum": ["billing"]}}

    scorer = CompositeScorer(
        [RefusalScorer(), JsonSchemaScorer(schema)]
    )

    # Both pass
    output = {"category": "billing"}
    assert scorer.score(output) == 1.0

    # One fails (refusal)
    output = {"category": "I cannot help"}
    score = scorer.score(output)
    # Refusal: 0.0, JSON: 0.0 (invalid enum) => avg = 0.0
    assert score == 0.0

    # Schema fails, refusal passes
    output = {"category": "wrong"}
    score = scorer.score(output)
    # Refusal: 1.0, JSON: 0.0 => avg = 0.5
    assert score == 0.5


def test_composite_scorer_custom_weights():
    schema = {"category": {"type": "string", "enum": ["billing"]}}

    scorer = CompositeScorer(
        [RefusalScorer(), JsonSchemaScorer(schema)],
        weights=[0.7, 0.3]
    )

    # Schema fails, refusal passes
    output = {"category": "wrong"}
    score = scorer.score(output)
    # Refusal: 1.0 * 0.7 = 0.7, JSON: 0.0 * 0.3 = 0.0 => total = 0.7
    assert abs(score - 0.7) < 1e-6


def test_composite_scorer_weights_validation():
    try:
        CompositeScorer([RefusalScorer()], weights=[0.5, 0.5])
        assert False, "Should raise ValueError"
    except ValueError as e:
        assert "must match" in str(e)

    try:
        CompositeScorer([RefusalScorer()], weights=[0.5])
        assert False, "Should raise ValueError"
    except ValueError as e:
        assert "sum to 1.0" in str(e)


def test_baseline_store_basic():
    """Test basic store and retrieve."""
    tmpdir = tempfile.mkdtemp()
    try:
        store = BaselineStore(storage_dir=tmpdir)

        # Store a baseline
        output = {"category": "billing", "priority": "high", "summary": "Test"}
        store.store("test-run-1", output, 0.85)

        # Retrieve it
        baseline = store.get("test-run-1")
        assert baseline is not None
        assert baseline["run_id"] == "test-run-1"
        assert baseline["output"] == output
        assert baseline["score"] == 0.85
    finally:
        shutil.rmtree(tmpdir)


def test_baseline_store_not_found():
    """Test retrieving non-existent baseline."""
    tmpdir = tempfile.mkdtemp()
    try:
        store = BaselineStore(storage_dir=tmpdir)
        baseline = store.get("nonexistent")
        assert baseline is None
    finally:
        shutil.rmtree(tmpdir)


def test_baseline_store_exists():
    """Test exists check."""
    tmpdir = tempfile.mkdtemp()
    try:
        store = BaselineStore(storage_dir=tmpdir)

        assert store.exists("test-run") is False

        store.store("test-run", "output", 0.9)

        assert store.exists("test-run") is True
    finally:
        shutil.rmtree(tmpdir)


def test_baseline_store_delete():
    """Test deletion."""
    tmpdir = tempfile.mkdtemp()
    try:
        store = BaselineStore(storage_dir=tmpdir)

        store.store("test-run", "output", 0.9)
        assert store.exists("test-run") is True

        deleted = store.delete("test-run")
        assert deleted is True
        assert store.exists("test-run") is False

        # Delete again should return False
        deleted = store.delete("test-run")
        assert deleted is False
    finally:
        shutil.rmtree(tmpdir)


def test_baseline_store_validation():
    """Test score validation."""
    tmpdir = tempfile.mkdtemp()
    try:
        store = BaselineStore(storage_dir=tmpdir)

        try:
            store.store("test", "output", 1.5)
            assert False, "Should raise ValueError"
        except ValueError as e:
            assert "score must be between 0 and 1" in str(e)
    finally:
        shutil.rmtree(tmpdir)


if __name__ == "__main__":
    # Run tests
    test_refusal_scorer_detects_refusals()
    test_refusal_scorer_with_dict()
    test_json_schema_scorer_valid()
    test_json_schema_scorer_partial()
    test_json_schema_scorer_invalid_enum()
    test_json_schema_scorer_empty_string()
    test_json_schema_scorer_with_string_input()
    test_composite_scorer_equal_weights()
    test_composite_scorer_custom_weights()
    test_composite_scorer_weights_validation()
    test_baseline_store_basic()
    test_baseline_store_not_found()
    test_baseline_store_exists()
    test_baseline_store_delete()
    test_baseline_store_validation()
    print("All tests passed!")

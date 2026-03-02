"""
Tests for CLI functionality.
"""
import json
import sys
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from cli.main import load_cases_file, run_command
from core.baselines import BaselineStore


def test_load_cases_file():
    """Test loading cases from JSON file."""
    tmpfile = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
    try:
        cases_data = {
            "run_id": "test",
            "schema": {"field": {"type": "string"}},
            "outputs": [{"field": "value"}]
        }
        json.dump(cases_data, tmpfile)
        tmpfile.close()

        loaded = load_cases_file(tmpfile.name)
        assert loaded["run_id"] == "test"
        assert "schema" in loaded
        assert len(loaded["outputs"]) == 1
    finally:
        Path(tmpfile.name).unlink()


def test_run_command_creates_baseline():
    """Test that first run creates a baseline."""
    tmpdir = tempfile.mkdtemp()
    tmpfile = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')

    try:
        # Create test cases
        cases = {
            "run_id": "test_run",
            "schema": {
                "category": {"type": "string", "enum": ["a", "b"]},
                "summary": {"type": "string"}
            },
            "scorer_weights": {"refusal": 0.3, "schema": 0.7},
            "outputs": [
                {"category": "a", "summary": "Test 1"},
                {"category": "b", "summary": "Test 2"}
            ]
        }
        json.dump(cases, tmpfile)
        tmpfile.close()

        # Mock args
        class Args:
            cases = tmpfile.name
            baseline = tmpdir
            threshold = 0.1
            run_id = None

        args = Args()

        # Run command (should create baseline)
        exit_code = run_command(args)

        # Should pass (baseline created)
        assert exit_code == 0

        # Verify baseline was stored
        store = BaselineStore(storage_dir=tmpdir)
        baseline = store.get("test_run")
        assert baseline is not None
        assert baseline["score"] == 1.0  # Both outputs are perfect

    finally:
        Path(tmpfile.name).unlink()
        shutil.rmtree(tmpdir)


def test_run_command_passes_with_good_outputs():
    """Test that good outputs pass regression check."""
    tmpdir = tempfile.mkdtemp()
    tmpfile = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')

    try:
        # Create baseline
        store = BaselineStore(storage_dir=tmpdir)
        store.store("test_run", {"category": "a", "summary": "Base"}, 1.0)

        # Create test cases (same quality)
        cases = {
            "run_id": "test_run",
            "schema": {
                "category": {"type": "string", "enum": ["a", "b"]},
                "summary": {"type": "string"}
            },
            "scorer_weights": {"refusal": 0.3, "schema": 0.7},
            "outputs": [
                {"category": "a", "summary": "Test 1"},
                {"category": "b", "summary": "Test 2"}
            ]
        }
        json.dump(cases, tmpfile)
        tmpfile.close()

        class Args:
            cases = tmpfile.name
            baseline = tmpdir
            threshold = 0.1
            run_id = None

        args = Args()
        exit_code = run_command(args)

        # Should pass (no regression)
        assert exit_code == 0

    finally:
        Path(tmpfile.name).unlink()
        shutil.rmtree(tmpdir)


def test_run_command_fails_with_bad_outputs():
    """Test that degraded outputs fail regression check."""
    tmpdir = tempfile.mkdtemp()
    tmpfile = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')

    try:
        # Create baseline with high score
        store = BaselineStore(storage_dir=tmpdir)
        store.store("test_run", {"category": "a", "summary": "Base"}, 1.0)

        # Create test cases with missing fields (low quality)
        cases = {
            "run_id": "test_run",
            "schema": {
                "category": {"type": "string", "enum": ["a", "b"]},
                "summary": {"type": "string"}
            },
            "scorer_weights": {"refusal": 0.3, "schema": 0.7},
            "outputs": [
                {"category": "a"},  # Missing summary
                {"summary": "Test"}  # Missing category
            ]
        }
        json.dump(cases, tmpfile)
        tmpfile.close()

        class Args:
            cases = tmpfile.name
            baseline = tmpdir
            threshold = 0.1
            run_id = None

        args = Args()
        exit_code = run_command(args)

        # Should fail (regression detected)
        assert exit_code == 1

    finally:
        Path(tmpfile.name).unlink()
        shutil.rmtree(tmpdir)


def test_run_command_respects_threshold():
    """Test that threshold is respected."""
    tmpdir = tempfile.mkdtemp()
    tmpfile = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')

    try:
        # Create baseline
        store = BaselineStore(storage_dir=tmpdir)
        store.store("test_run", {"category": "a", "summary": "Base"}, 1.0)

        # Create test cases with slight degradation
        cases = {
            "run_id": "test_run",
            "schema": {
                "category": {"type": "string", "enum": ["a", "b"]},
                "summary": {"type": "string"}
            },
            "scorer_weights": {"refusal": 0.3, "schema": 0.7},
            "outputs": [
                {"category": "a", "summary": "Good"},
                {"category": "b"}  # Missing summary (scores 0.5)
            ]
        }
        json.dump(cases, tmpfile)
        tmpfile.close()

        # With high threshold (0.4), should pass
        class Args:
            cases = tmpfile.name
            baseline = tmpdir
            threshold = 0.4
            run_id = None

        args = Args()
        exit_code = run_command(args)
        assert exit_code == 0

        # With low threshold (0.1), should fail
        args.threshold = 0.1
        exit_code = run_command(args)
        assert exit_code == 1

    finally:
        Path(tmpfile.name).unlink()
        shutil.rmtree(tmpdir)


if __name__ == "__main__":
    test_load_cases_file()
    test_run_command_creates_baseline()
    test_run_command_passes_with_good_outputs()
    test_run_command_fails_with_bad_outputs()
    test_run_command_respects_threshold()
    print("All CLI tests passed!")

"""
Tests for cloud upload functionality.
"""
import sys
import json
import subprocess
import tempfile
from pathlib import Path
from unittest import mock
import urllib.error

sys.path.insert(0, str(Path(__file__).parent.parent))

from cloud.client import upload_run, get_error_message


def test_upload_run_success():
    """Test successful cloud upload."""
    report = {
        "tool_version": "0.6.0",
        "run_id": "test-run",
        "timestamp_utc": "2024-01-01T00:00:00+00:00",
        "overall": {"baseline_avg": 0.9, "new_avg": 0.85, "delta": -0.05, "verdict": "PASS"}
    }

    mock_response = mock.Mock()
    mock_response.read.return_value = json.dumps({"run_url": "https://app.ai-regression-guard.com/runs/123"}).encode('utf-8')
    mock_response.__enter__ = mock.Mock(return_value=mock_response)
    mock_response.__exit__ = mock.Mock(return_value=False)

    with mock.patch('urllib.request.urlopen', return_value=mock_response) as mock_urlopen:
        result = upload_run(report, "https://api.test.com", "test-key", "test-project")

        assert result == "https://app.ai-regression-guard.com/runs/123"

        # Verify request was made
        assert mock_urlopen.called
        request = mock_urlopen.call_args[0][0]
        assert request.get_method() == 'POST'
        assert request.full_url == "https://api.test.com/v1/runs"
        assert request.headers['Authorization'] == 'Bearer test-key'
        assert request.headers['Content-type'] == 'application/json'


def test_upload_run_http_error():
    """Test cloud upload with HTTP error."""
    report = {"tool_version": "0.6.0", "run_id": "test-run"}

    mock_error = urllib.error.HTTPError(
        url="https://api.test.com/v1/runs",
        code=500,
        msg="Internal Server Error",
        hdrs={},
        fp=None
    )

    with mock.patch('urllib.request.urlopen', side_effect=mock_error):
        try:
            upload_run(report, "https://api.test.com", "test-key", "test-project")
            assert False, "Should have raised HTTPError"
        except urllib.error.HTTPError as e:
            assert e.code == 500


def test_upload_run_network_error():
    """Test cloud upload with network error."""
    report = {"tool_version": "0.6.0", "run_id": "test-run"}

    mock_error = urllib.error.URLError("Connection refused")

    with mock.patch('urllib.request.urlopen', side_effect=mock_error):
        try:
            upload_run(report, "https://api.test.com", "test-key", "test-project")
            assert False, "Should have raised URLError"
        except urllib.error.URLError:
            pass


def test_upload_run_missing_run_url():
    """Test cloud upload with invalid API response."""
    report = {"tool_version": "0.6.0", "run_id": "test-run"}

    mock_response = mock.Mock()
    mock_response.read.return_value = json.dumps({"status": "ok"}).encode('utf-8')
    mock_response.__enter__ = mock.Mock(return_value=mock_response)
    mock_response.__exit__ = mock.Mock(return_value=False)

    with mock.patch('urllib.request.urlopen', return_value=mock_response):
        try:
            upload_run(report, "https://api.test.com", "test-key", "test-project")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "run_url" in str(e)


def test_get_error_message():
    """Test error message extraction."""
    # HTTP error
    http_error = urllib.error.HTTPError(
        url="https://api.test.com",
        code=404,
        msg="Not Found",
        hdrs={},
        fp=None
    )
    assert get_error_message(http_error) == "HTTP 404"

    # URL error
    url_error = urllib.error.URLError("Connection refused")
    assert get_error_message(url_error) == "Network error"

    # Timeout
    timeout_error = TimeoutError()
    assert get_error_message(timeout_error) == "Request timeout"

    # Value error
    value_error = ValueError("Invalid response")
    assert get_error_message(value_error) == "Invalid response"

    # Unknown error
    unknown_error = RuntimeError("Something went wrong")
    assert get_error_message(unknown_error) == "Unknown error"


def test_cli_cloud_flag_recognized():
    """Test CLI recognizes --cloud flags without actual upload."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create suite
        suite = {
            "run_id": "cloud-test",
            "prompt_template": "Test: {text}",
            "schema": {"category": {"type": "string"}},
            "cases": [{"id": "case1", "input": {"text": "test"}}]
        }

        suite_file = tmpdir_path / "suite.json"
        with open(suite_file, "w") as f:
            json.dump(suite, f)

        # Create baseline
        baseline_dir = tmpdir_path / ".baselines"
        baseline_dir.mkdir()

        baseline = {
            "run_id": "cloud-test",
            "overall_avg": 0.9,
            "per_case_scores": {
                "case1": {
                    "total": 0.9,
                    "scorers": {"refusal_detection": 1.0, "json_schema": 0.8},
                    "judge_reason": None
                }
            }
        }

        baseline_file = baseline_dir / "cloud-test.json"
        with open(baseline_file, "w") as f:
            json.dump(baseline, f)

        # Run check with --cloud but invalid API endpoint (will fail)
        cmd = [
            sys.executable, "-m", "cli.main", "check",
            "--suite", str(suite_file),
            "--provider", "fake",
            "--model", "test",
            "--baseline", str(baseline_dir),
            "--cloud",
            "--cloud-url", "https://invalid.example.com",
            "--cloud-project", "test-project",
            "--cloud-api-key", "test-key"
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent)
        )

        # Check that cloud upload was attempted (will fail with warning)
        assert "Cloud upload failed" in result.stdout or "CLOUD REPORT:" in result.stdout
        # Check exit code is still 0 (no regression, cloud failure doesn't affect it)
        assert result.returncode == 0


def test_cli_cloud_upload_missing_api_key():
    """Test CLI with --cloud but no API key."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create minimal suite and baseline
        suite = {
            "run_id": "cloud-test-no-key",
            "prompt_template": "Test: {text}",
            "schema": {"category": {"type": "string"}},
            "cases": [{"id": "case1", "input": {"text": "test"}}]
        }

        suite_file = tmpdir_path / "suite.json"
        with open(suite_file, "w") as f:
            json.dump(suite, f)

        baseline_dir = tmpdir_path / ".baselines"
        baseline_dir.mkdir()

        baseline = {
            "run_id": "cloud-test-no-key",
            "overall_avg": 0.9,
            "per_case_scores": {
                "case1": {
                    "total": 0.9,
                    "scorers": {"refusal_detection": 1.0},
                    "judge_reason": None
                }
            }
        }

        baseline_file = baseline_dir / "cloud-test-no-key.json"
        with open(baseline_file, "w") as f:
            json.dump(baseline, f)

        # Run check with --cloud but no API key
        cmd = [
            sys.executable, "-m", "cli.main", "check",
            "--suite", str(suite_file),
            "--provider", "fake",
            "--model", "test",
            "--baseline", str(baseline_dir),
            "--cloud",
            "--cloud-project", "test-project"
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent),
            env={k: v for k, v in __import__('os').environ.items() if k != 'AIRG_API_KEY'}
        )

        # Check that warning was printed
        assert "No API key provided" in result.stdout
        # Check exit code is still 0 (no regression)
        assert result.returncode == 0


def test_cli_cloud_upload_failure_does_not_change_exit_code():
    """Test that cloud upload failure doesn't affect CI exit code."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create suite and baseline
        suite = {
            "run_id": "cloud-test-fail",
            "prompt_template": "Test: {text}",
            "schema": {"category": {"type": "string"}},
            "cases": [{"id": "case1", "input": {"text": "test"}}]
        }

        suite_file = tmpdir_path / "suite.json"
        with open(suite_file, "w") as f:
            json.dump(suite, f)

        baseline_dir = tmpdir_path / ".baselines"
        baseline_dir.mkdir()

        baseline = {
            "run_id": "cloud-test-fail",
            "overall_avg": 0.9,
            "per_case_scores": {
                "case1": {
                    "total": 0.9,
                    "scorers": {"refusal_detection": 1.0},
                    "judge_reason": None
                }
            }
        }

        baseline_file = baseline_dir / "cloud-test-fail.json"
        with open(baseline_file, "w") as f:
            json.dump(baseline, f)

        # Mock cloud upload to fail
        mock_error = urllib.error.HTTPError(
            url="https://api.ai-regression-guard.com/v1/runs",
            code=500,
            msg="Internal Server Error",
            hdrs={},
            fp=None
        )

        with mock.patch('urllib.request.urlopen', side_effect=mock_error):
            # Run check with --cloud
            cmd = [
                sys.executable, "-m", "cli.main", "check",
                "--suite", str(suite_file),
                "--provider", "fake",
                "--model", "test",
                "--baseline", str(baseline_dir),
                "--cloud",
                "--cloud-project", "test-project",
                "--cloud-api-key", "test-key"
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(Path(__file__).parent.parent)
            )

            # Check that warning was printed
            assert "Cloud upload failed" in result.stdout
            # Check exit code is still 0 (no regression, cloud failure doesn't affect it)
            assert result.returncode == 0


if __name__ == "__main__":
    print("Running cloud upload tests...\n")

    test_upload_run_success()
    print("[PASS] test_upload_run_success")

    test_upload_run_http_error()
    print("[PASS] test_upload_run_http_error")

    test_upload_run_network_error()
    print("[PASS] test_upload_run_network_error")

    test_upload_run_missing_run_url()
    print("[PASS] test_upload_run_missing_run_url")

    test_get_error_message()
    print("[PASS] test_get_error_message")

    test_cli_cloud_flag_recognized()
    print("[PASS] test_cli_cloud_flag_recognized")

    test_cli_cloud_upload_missing_api_key()
    print("[PASS] test_cli_cloud_upload_missing_api_key")

    test_cli_cloud_upload_failure_does_not_change_exit_code()
    print("[PASS] test_cli_cloud_upload_failure_does_not_change_exit_code")

    print("\nAll cloud upload tests passed!")

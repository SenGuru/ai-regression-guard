"""
Cloud upload client for ai-regression-guard.

Uploads run reports to the hosted API and returns shareable URLs.
"""
import json
import urllib.request
import urllib.error
from typing import Optional


def upload_run(
    report: dict,
    cloud_url: str,
    api_key: str,
    project: str,
    timeout: int = 10
) -> str:
    """
    Upload a run report to the cloud API.

    Args:
        report: The run report data to upload
        cloud_url: Base URL of the cloud API (e.g., https://api.ai-regression-guard.com)
        api_key: API key for authentication
        project: Project identifier/slug
        timeout: Request timeout in seconds (default: 10)

    Returns:
        The shareable run URL from the API response

    Raises:
        urllib.error.URLError: If the request fails
        ValueError: If the API response is invalid
    """
    # Add project to report
    report_with_project = {
        **report,
        "project": project
    }

    # Prepare request
    endpoint = f"{cloud_url.rstrip('/')}/v1/runs"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    data = json.dumps(report_with_project).encode('utf-8')

    request = urllib.request.Request(
        endpoint,
        data=data,
        headers=headers,
        method='POST'
    )

    # Make request with retry
    max_retries = 2
    last_error = None

    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                response_data = json.loads(response.read().decode('utf-8'))

                if "run_url" not in response_data:
                    raise ValueError("API response missing 'run_url' field")

                return response_data["run_url"]

        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            last_error = e
            if attempt < max_retries - 1:
                # Retry once
                continue
            else:
                # Final attempt failed
                raise last_error
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON response from API: {e}")

    # Should not reach here, but just in case
    if last_error:
        raise last_error
    raise RuntimeError("Upload failed with unknown error")


def get_error_message(error: Exception) -> str:
    """
    Extract a safe, concise error message from an exception.

    Does not leak sensitive information like API keys or full URLs.
    """
    if isinstance(error, urllib.error.HTTPError):
        return f"HTTP {error.code}"
    elif isinstance(error, urllib.error.URLError):
        if isinstance(error.reason, TimeoutError):
            return "Request timeout"
        return "Network error"
    elif isinstance(error, ValueError):
        return str(error)
    elif isinstance(error, TimeoutError):
        return "Request timeout"
    else:
        return "Unknown error"

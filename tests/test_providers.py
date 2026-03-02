"""
Tests for LLM providers.
"""
import json
import sys
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from providers import FakeProvider, get_provider
from providers.base import BaseProvider


def test_fake_provider_basic():
    """Test FakeProvider basic functionality."""
    provider = FakeProvider()

    # Test billing classification
    output = provider.generate("Customer can't pay their bill")
    result = json.loads(output)
    assert result["category"] == "billing"
    assert result["priority"] == "high"

    # Test technical classification
    output = provider.generate("API error 500")
    result = json.loads(output)
    assert result["category"] == "technical"
    assert result["priority"] == "medium"

    # Test account classification
    output = provider.generate("Update my email address")
    result = json.loads(output)
    assert result["category"] == "account"
    assert result["priority"] == "low"


def test_fake_provider_custom_responses():
    """Test FakeProvider with custom responses."""
    custom_responses = {
        "hello": '{"greeting": "world"}',
        "test": '{"result": "passed"}'
    }

    provider = FakeProvider(responses=custom_responses)

    output = provider.generate("Say hello to me")
    result = json.loads(output)
    assert result["greeting"] == "world"

    output = provider.generate("Run test suite")
    result = json.loads(output)
    assert result["result"] == "passed"


def test_fake_provider_call_tracking():
    """Test that FakeProvider tracks calls."""
    provider = FakeProvider()

    assert provider.call_count == 0
    assert provider.last_prompt is None

    provider.generate("Test prompt 1")
    assert provider.call_count == 1
    assert provider.last_prompt == "Test prompt 1"

    provider.generate("Test prompt 2")
    assert provider.call_count == 2
    assert provider.last_prompt == "Test prompt 2"


def test_fake_provider_name():
    """Test provider name property."""
    provider = FakeProvider()
    assert provider.name == "fake/test-model"


def test_get_provider_factory():
    """Test provider factory function."""
    # Test fake provider
    provider = get_provider("fake", "test-model")
    assert isinstance(provider, FakeProvider)
    assert provider.name == "fake/test-model"

    # Test unknown provider
    try:
        get_provider("unknown", "model")
        assert False, "Should raise ValueError"
    except ValueError as e:
        assert "Unknown provider" in str(e)


def test_openai_provider_initialization():
    """Test OpenAI provider can be initialized."""
    from providers.openai_provider import OpenAIProvider

    provider = OpenAIProvider(model="gpt-4")
    assert provider.model == "gpt-4"
    assert provider.name == "openai/gpt-4"


def test_anthropic_provider_initialization():
    """Test Anthropic provider can be initialized."""
    from providers.anthropic_provider import AnthropicProvider

    provider = AnthropicProvider(model="claude-3-5-sonnet-20241022")
    assert provider.model == "claude-3-5-sonnet-20241022"
    assert provider.name == "anthropic/claude-3-5-sonnet-20241022"


def test_openai_provider_requires_api_key():
    """Test OpenAI provider requires API key or raises import error."""
    from providers.openai_provider import OpenAIProvider

    provider = OpenAIProvider(model="gpt-4")

    # Should raise either ImportError (package not installed) or ValueError (no API key)
    with patch.dict('os.environ', {}, clear=True):
        try:
            provider.generate("test")
            assert False, "Should raise ImportError or ValueError"
        except (ImportError, ValueError) as e:
            # Either error is acceptable
            assert "openai" in str(e).lower() or "OPENAI_API_KEY" in str(e)


def test_anthropic_provider_requires_api_key():
    """Test Anthropic provider requires API key or raises import error."""
    from providers.anthropic_provider import AnthropicProvider

    provider = AnthropicProvider()

    # Should raise either ImportError (package not installed) or ValueError (no API key)
    with patch.dict('os.environ', {}, clear=True):
        try:
            provider.generate("test")
            assert False, "Should raise ImportError or ValueError"
        except (ImportError, ValueError) as e:
            # Either error is acceptable
            assert "anthropic" in str(e).lower() or "ANTHROPIC_API_KEY" in str(e)


if __name__ == "__main__":
    test_fake_provider_basic()
    test_fake_provider_custom_responses()
    test_fake_provider_call_tracking()
    test_fake_provider_name()
    test_get_provider_factory()
    test_openai_provider_initialization()
    test_anthropic_provider_initialization()
    test_openai_provider_requires_api_key()
    test_anthropic_provider_requires_api_key()
    print("All provider tests passed!")

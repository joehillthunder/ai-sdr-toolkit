import pytest

from sdr_toolkit.llm import (
    AnthropicLLMClient,
    MockLLMClient,
    OpenAICompatibleLLMClient,
    OpenAILLMClient,
    get_client,
)


def test_get_client_defaults_to_mock():
    assert isinstance(get_client(), MockLLMClient)
    assert isinstance(get_client(live=False), MockLLMClient)
    assert isinstance(get_client(provider="demo"), MockLLMClient)
    assert isinstance(get_client(provider="offline"), MockLLMClient)


def test_get_client_live_flag_still_selects_anthropic_class(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-123")
    client = get_client(live=True)
    assert isinstance(client, AnthropicLLMClient)


def test_get_client_provider_aliases_resolve(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    assert isinstance(get_client(provider="claude"), AnthropicLLMClient)
    assert isinstance(get_client(provider="anthropic"), AnthropicLLMClient)
    assert isinstance(get_client(provider="openai"), OpenAILLMClient)
    assert isinstance(get_client(provider="open-source", model="llama3.1"), OpenAICompatibleLLMClient)
    assert isinstance(get_client(provider="ollama", model="llama3.1"), OpenAICompatibleLLMClient)


def test_get_client_unknown_provider_raises():
    with pytest.raises(ValueError):
        get_client(provider="not-a-real-provider")


def test_anthropic_client_requires_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        AnthropicLLMClient()


def test_openai_client_requires_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        OpenAILLMClient()


def test_open_source_client_does_not_require_api_key():
    # Local/open-source servers usually accept a placeholder key -- this
    # should construct fine even with nothing set. It doesn't make a
    # network call until .generate() is invoked.
    client = OpenAICompatibleLLMClient(model="llama3.1", base_url="http://localhost:11434/v1")
    assert client.name == "open-source"


def test_mock_client_covers_every_agent_contract():
    llm = MockLLMClient()
    assert "SUMMARY:" in llm.generate("You are building a dossier.", "x")
    assert "TOUCH_1_EMAIL_SUBJECT:" in llm.generate("Write an outreach sequence.", "x")
    assert "VERDICT:" in llm.generate("You do qualification.", "x")
    assert "INDUSTRIES:" in llm.generate("Build an Ideal Customer Profile for go-to-market.", "x")
    assert llm.generate("Something else entirely.", "x") == "OK"

"""LLM client abstraction.

Everything in agents.py and icp_builder.py talks to an `LLMClient`, never
to a specific SDK. `MockLLMClient` is deterministic and offline — it's
what tests and `sdr-toolkit demo` use by default, so the whole repo is
clonable and runnable with zero API keys.

Three real providers are supported, all behind the same interface:
`AnthropicLLMClient` (Claude), `OpenAILLMClient` (OpenAI), and
`OpenAICompatibleLLMClient` — any server that speaks the OpenAI chat
completions wire format, which covers "open source models" in practice:
a local Ollama or LM Studio server, vLLM, or a hosted open-weights
provider like Together/Groq/Fireworks. Pick one via `get_client(provider=...)`.
"""

from __future__ import annotations

import os
from typing import Protocol


class LLMClient(Protocol):
    def generate(self, system: str, prompt: str) -> str:
        ...


class MockLLMClient:
    """Deterministic, template-based stand-in for a real model. Produces
    plausible, structured output so downstream parsing and tests behave
    the same as they would against a live model."""

    name = "mock"

    def generate(self, system: str, prompt: str) -> str:
        # Deterministic "generation": echoes structure back based on simple
        # heuristics over the prompt so callers get realistic, parseable
        # text without any network access.
        system_lower = system.lower()
        if "dossier" in system_lower:
            return self._dossier(prompt)
        if "additional outreach touch" in system_lower:
            return self._channel_touch(prompt)
        if "sequence" in system_lower or "outreach" in system_lower:
            return self._sequence(prompt)
        if "qualif" in system_lower:
            return self._qualification(prompt)
        if "brainstorming" in system_lower or "market researcher" in system_lower:
            return self._research(prompt)
        if "ideal customer profile" in system_lower or "go-to-market" in system_lower:
            return self._icp(prompt)
        return "OK"

    @staticmethod
    def _dossier(prompt: str) -> str:
        return (
            "SUMMARY: This account shows active buying signals worth engaging now.\n"
            "PAIN_POINTS: Scaling engineering headcount faster than infra can support; "
            "evaluating build-vs-buy on core AI capability.\n"
            "ANGLE: Lead with the specific signal in the prompt context and tie it to "
            "time-to-value, not a generic feature pitch."
        )

    @staticmethod
    def _sequence(prompt: str) -> str:
        return (
            "TOUCH_1_EMAIL_SUBJECT: Quick question about your recent hiring push\n"
            "TOUCH_1_EMAIL_BODY: Saw the signal referenced above — congrats. Most teams "
            "in that spot hit the same wall about 60 days later. Worth 15 minutes?\n"
            "TOUCH_2_LINKEDIN_BODY: Following up on my note — happy to share what similar "
            "teams did here, no pitch needed if it's not a fit.\n"
            "TOUCH_3_EMAIL_SUBJECT: Closing the loop\n"
            "TOUCH_3_EMAIL_BODY: Didn't want this to sit in your inbox forever. I'll leave "
            "the door open — reach out whenever the timing's better."
        )

    @staticmethod
    def _qualification(prompt: str) -> str:
        return (
            "VERDICT: qualified\n"
            "RATIONALE: Signal strength and ICP fit both support prioritizing this account "
            "for immediate rep outreach."
        )

    @staticmethod
    def _icp(prompt: str) -> str:
        return (
            "INDUSTRIES: technology, professional services, retail\n"
            "MIN_EMPLOYEES: 10\n"
            "MAX_EMPLOYEES: 500\n"
            "DESCRIPTION_KEYWORDS: growth, team, customers, platform, service\n"
            "HIRING_KEYWORDS: operations, sales, account manager, marketing\n"
            "TECH_KEYWORDS: crm, automation, analytics\n"
            "WEBSITE_KEYWORDS: solutions, platform, trusted by"
        )

    @staticmethod
    def _channel_touch(prompt: str) -> str:
        return "BODY: Saw the signal referenced above and thought it was worth a note — happy to share more if useful, no pressure either way."

    @staticmethod
    def _research(prompt: str) -> str:
        return (
            "1. Sample Robotics Co — Matches target industry and headcount range.\n"
            "2. Placeholder Analytics Inc — Frequently hiring roles matching your signal keywords.\n"
            "3. Demo Cloud Systems — Public homepage language closely matches your ICP terms.\n"
            "4. Northwind Data Labs — Recently funded and in your target size range.\n"
            "5. Bluepeak Software — Industry and description keywords both match."
        )


class AnthropicLLMClient:
    """Thin wrapper around the Anthropic Messages API."""

    name = "claude"

    def __init__(self, model: str = "claude-sonnet-5", api_key: str | None = None, max_tokens: int = 600):
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "The 'anthropic' package is required for live mode. "
                "Install it with `pip install anthropic` (or `pip install -e '.[live]'`)."
            ) from exc

        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Export it, pass an api_key, or run "
                "without --live to use the offline mock client."
            )
        self._client = anthropic.Anthropic(api_key=key)
        self.model = model
        self.max_tokens = max_tokens

    def generate(self, system: str, prompt: str) -> str:
        response = self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(
            block.text for block in response.content if getattr(block, "type", None) == "text"
        )


class OpenAILLMClient:
    """Thin wrapper around the OpenAI chat completions API."""

    name = "openai"

    def __init__(self, model: str = "gpt-4o-mini", api_key: str | None = None, max_tokens: int = 600):
        try:
            import openai
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "The 'openai' package is required for the OpenAI provider. "
                "Install it with `pip install openai` (or `pip install -e '.[openai]'`)."
            ) from exc

        key = api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("OPENAI_API_KEY is not set. Export it or pass an api_key.")
        self._client = openai.OpenAI(api_key=key)
        self.model = model
        self.max_tokens = max_tokens

    def generate(self, system: str, prompt: str) -> str:
        response = self._client.chat.completions.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content or ""


class OpenAICompatibleLLMClient:
    """Any server that speaks the OpenAI chat-completions wire format.

    This is the "open source models" option: point `base_url` at a local
    Ollama (`http://localhost:11434/v1`) or LM Studio server, a self-hosted
    vLLM/TGI endpoint, or a hosted open-weights provider (Together, Groq,
    Fireworks, ...). No Anthropic/OpenAI account required — most local
    servers accept any placeholder string as the API key.
    """

    name = "open-source"

    def __init__(
        self,
        model: str,
        base_url: str = "http://localhost:11434/v1",
        api_key: str | None = None,
        max_tokens: int = 600,
    ):
        try:
            import openai
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "The 'openai' package is required as the HTTP client for "
                "OpenAI-compatible servers (including local/open-source ones). "
                "Install it with `pip install openai` (or `pip install -e '.[openai]'`)."
            ) from exc

        self._client = openai.OpenAI(base_url=base_url, api_key=api_key or "not-needed")
        self.model = model
        self.max_tokens = max_tokens

    def generate(self, system: str, prompt: str) -> str:
        response = self._client.chat.completions.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content or ""


_PROVIDER_ALIASES = {
    "mock": "mock", "offline": "mock", "demo": "mock",
    "anthropic": "anthropic", "claude": "anthropic",
    "openai": "openai", "gpt": "openai",
    "open-source": "open-source", "opensource": "open-source",
    "local": "open-source", "ollama": "open-source",
}


def get_client(
    live: bool = False,
    provider: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
) -> LLMClient:
    """Build an LLM client.

    Two ways to call this: the simple CLI path (`live=True/False`, always
    Claude-or-mock), or the explicit path used by the wizard web app
    (`provider=...`, one of mock/anthropic/openai/open-source).
    """
    if provider is None:
        provider = "anthropic" if live else "mock"

    resolved = _PROVIDER_ALIASES.get((provider or "mock").lower())
    if resolved is None:
        raise ValueError(f"Unknown LLM provider: {provider!r}")

    if resolved == "mock":
        return MockLLMClient()
    if resolved == "anthropic":
        return AnthropicLLMClient(model=model or "claude-sonnet-5", api_key=api_key)
    if resolved == "openai":
        return OpenAILLMClient(model=model or "gpt-4o-mini", api_key=api_key)
    if resolved == "open-source":
        return OpenAICompatibleLLMClient(
            model=model or "llama3.1",
            base_url=base_url or "http://localhost:11434/v1",
            api_key=api_key,
        )
    raise ValueError(f"Unknown LLM provider: {provider!r}")  # pragma: no cover

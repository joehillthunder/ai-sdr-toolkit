"""LLM client abstraction.

Everything in agents.py talks to an `LLMClient`, never to a specific SDK.
`MockLLMClient` is deterministic and offline — it's what tests and
`sdr-toolkit demo` use by default, so the whole repo is clonable and
runnable with zero API keys. `AnthropicLLMClient` calls Claude for real
when ANTHROPIC_API_KEY is set and `--live` is passed to the CLI.
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
        if "dossier" in system.lower():
            return self._dossier(prompt)
        if "sequence" in system.lower() or "outreach" in system.lower():
            return self._sequence(prompt)
        if "qualif" in system.lower():
            return self._qualification(prompt)
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


class AnthropicLLMClient:
    """Thin wrapper around the Anthropic Messages API."""

    def __init__(self, model: str = "claude-sonnet-5", max_tokens: int = 600):
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "The 'anthropic' package is required for live mode. "
                "Install it with `pip install anthropic`."
            ) from exc

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Export it or run without --live "
                "to use the offline mock client."
            )
        self._client = anthropic.Anthropic(api_key=api_key)
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


def get_client(live: bool = False, model: str = "claude-sonnet-5") -> LLMClient:
    if live:
        return AnthropicLLMClient(model=model)
    return MockLLMClient()

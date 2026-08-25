"""Concrete signal source adapters.

Each source here defaults to the bundled offline demo dataset so the
pipeline works with zero credentials. `HiringSurgeSignalSource` and
`WebsiteChangeSignalSource` also support a `live=True` mode that makes
real, unauthenticated HTTP calls (Greenhouse's public job board API,
and the company's own homepage) — genuinely live signals with no API
key required. Real BuiltWith/Crunchbase/Apollo/Clay connectors would
slot in the same way: implement `SignalSource.collect`.
"""

from __future__ import annotations

import uuid
import warnings

from ..models import Company, Signal
from .base import SignalSource, recency_decay
from .demo_data import FUNDING_EVENTS, JOB_POSTINGS, TECH_MENTIONS, WEBSITE_SNIPPETS, TODAY, days_ago

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None


def _uid() -> str:
    return uuid.uuid4().hex[:12]


def _keyword_matches(text: str, keywords: list[str]) -> list[str]:
    text_lower = text.lower()
    return [kw for kw in keywords if kw.lower() in text_lower]


class HiringSurgeSignalSource(SignalSource):
    """Detects hiring surges in roles relevant to the ICP.

    Offline mode reads the bundled sample job postings. Live mode queries
    Greenhouse's public (no-auth) job board API for companies that expose
    one, via `greenhouse_tokens={company_id: board_token}`.
    """

    name = "hiring_surge"

    def __init__(
        self,
        keywords: list[str],
        live: bool = False,
        greenhouse_tokens: dict[str, str] | None = None,
        timeout: float = 5.0,
    ):
        self.keywords = keywords
        self.live = live
        self.greenhouse_tokens = greenhouse_tokens or {}
        self.timeout = timeout

    def collect(self, companies: list[Company]) -> list[Signal]:
        signals: list[Signal] = []
        for company in companies:
            postings = self._fetch(company)
            matched_titles = [
                title for title, _ in postings if _keyword_matches(title, self.keywords)
            ]
            if not matched_titles:
                continue
            most_recent_days_ago = min(d for t, d in postings if t in matched_titles)
            detected = days_ago(most_recent_days_ago)
            base_strength = min(1.0, len(matched_titles) / 3)
            strength = round(base_strength * recency_decay(detected, TODAY), 3)
            signals.append(
                Signal(
                    id=_uid(),
                    company_id=company.id,
                    type=self.name,
                    strength=strength,
                    detected_at=detected,
                    evidence=f"{len(matched_titles)} relevant open role(s): "
                    + "; ".join(matched_titles[:4]),
                    source="live:greenhouse" if self.live else "demo:job_postings",
                )
            )
        return signals

    def _fetch(self, company: Company) -> list[tuple[str, int]]:
        if self.live and requests is not None and company.id in self.greenhouse_tokens:
            token = self.greenhouse_tokens[company.id]
            try:
                resp = requests.get(
                    f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs",
                    timeout=self.timeout,
                )
                resp.raise_for_status()
                jobs = resp.json().get("jobs", [])
                return [(job.get("title", ""), 0) for job in jobs]
            except Exception as exc:  # noqa: BLE001 - never let one source break a run
                warnings.warn(f"Greenhouse fetch failed for {company.name}: {exc}")
        return JOB_POSTINGS.get(company.id, [])


class FundingSignalSource(SignalSource):
    """Funding events. Offline-only in this repo; swap in Crunchbase/
    PitchBook/press-release monitoring for a live version."""

    name = "funding"

    def collect(self, companies: list[Company]) -> list[Signal]:
        signals = []
        for company in companies:
            for round_label, amount, dago in FUNDING_EVENTS.get(company.id, []):
                detected = days_ago(dago)
                strength = round(recency_decay(detected, TODAY, half_life_days=60), 3)
                signals.append(
                    Signal(
                        id=_uid(),
                        company_id=company.id,
                        type=self.name,
                        strength=strength,
                        detected_at=detected,
                        evidence=f"Raised ${amount / 1_000_000:.1f}M {round_label}",
                        source="demo:funding_events",
                    )
                )
        return signals


class TechAdoptionSignalSource(SignalSource):
    """Detects mentions of relevant technology adoption in public
    engineering blogs / changelogs / social posts."""

    name = "tech_adoption"

    def __init__(self, keywords: list[str]):
        self.keywords = keywords

    def collect(self, companies: list[Company]) -> list[Signal]:
        signals = []
        for company in companies:
            for text, dago in TECH_MENTIONS.get(company.id, []):
                matches = _keyword_matches(text, self.keywords)
                if not matches:
                    continue
                detected = days_ago(dago)
                base_strength = min(1.0, len(matches) / 2)
                strength = round(base_strength * recency_decay(detected, TODAY, half_life_days=45), 3)
                signals.append(
                    Signal(
                        id=_uid(),
                        company_id=company.id,
                        type=self.name,
                        strength=strength,
                        detected_at=detected,
                        evidence=text,
                        source="demo:tech_mentions",
                    )
                )
        return signals


class WebsiteChangeSignalSource(SignalSource):
    """Keyword-matches a company's homepage copy against ICP signal
    keywords. Offline mode uses a bundled snippet; live mode fetches the
    real homepage over HTTP with no API key required."""

    name = "website_change"

    def __init__(self, keywords: list[str], live: bool = False, timeout: float = 5.0):
        self.keywords = keywords
        self.live = live
        self.timeout = timeout

    def collect(self, companies: list[Company]) -> list[Signal]:
        signals = []
        for company in companies:
            text, source_label = self._fetch(company)
            matches = _keyword_matches(text, self.keywords)
            if not matches:
                continue
            strength = round(min(1.0, len(matches) / 3), 3)
            signals.append(
                Signal(
                    id=_uid(),
                    company_id=company.id,
                    type=self.name,
                    strength=strength,
                    detected_at=TODAY,
                    evidence=f"Homepage mentions: {', '.join(matches)}",
                    source=source_label,
                )
            )
        return signals

    def _fetch(self, company: Company) -> tuple[str, str]:
        if self.live and requests is not None:
            try:
                resp = requests.get(f"https://{company.domain}", timeout=self.timeout)
                resp.raise_for_status()
                return resp.text, "live:website"
            except Exception as exc:  # noqa: BLE001
                warnings.warn(f"Website fetch failed for {company.name}: {exc}")
        return WEBSITE_SNIPPETS.get(company.id, company.description), "demo:website_snippet"

from unittest.mock import patch

from sdr_toolkit.models import Company
from sdr_toolkit.signals.sources import CareersPageSignalSource

COMPANY = Company("acme", "Acme AI", "acme.example", "ai", 80, "SF", "desc")


class _FakeResponse:
    def __init__(self, ok: bool, text: str):
        self.ok = ok
        self.text = text


def test_careers_page_source_detects_keyword_match():
    with patch("sdr_toolkit.signals.sources.requests") as mock_requests:
        mock_requests.get.return_value = _FakeResponse(True, "We're hiring an AI Engineer and a Voice Designer!")
        signals = CareersPageSignalSource(["ai engineer", "voice"]).collect([COMPANY])

    assert len(signals) == 1
    assert signals[0].type == "hiring_surge"
    assert signals[0].source == "live:careers_page"
    assert "ai engineer" in signals[0].evidence.lower()


def test_careers_page_source_no_match_returns_no_signal():
    with patch("sdr_toolkit.signals.sources.requests") as mock_requests:
        mock_requests.get.return_value = _FakeResponse(True, "We sell artisanal candles.")
        signals = CareersPageSignalSource(["ai engineer"]).collect([COMPANY])
    assert signals == []


def test_careers_page_source_survives_network_failure():
    with patch("sdr_toolkit.signals.sources.requests") as mock_requests:
        mock_requests.get.side_effect = Exception("DNS failure")
        signals = CareersPageSignalSource(["ai engineer"]).collect([COMPANY])
    assert signals == []

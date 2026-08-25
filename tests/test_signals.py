from sdr_toolkit.config import ICPConfig
from sdr_toolkit.signals.demo_data import demo_companies
from sdr_toolkit.signals.sources import (
    FundingSignalSource,
    HiringSurgeSignalSource,
    TechAdoptionSignalSource,
    WebsiteChangeSignalSource,
)

ICP = ICPConfig.default()
COMPANIES = demo_companies()


def test_hiring_surge_source_only_flags_relevant_companies():
    source = HiringSurgeSignalSource(ICP.signal_keywords["hiring_surge"])
    signals = source.collect(COMPANIES)
    flagged = {s.company_id for s in signals}

    assert "nimbus-voice" in flagged
    assert "chatterbox" in flagged
    assert "ledger-peak" not in flagged  # compliance/payments roles, no AI hiring signal
    assert all(0.0 < s.strength <= 1.0 for s in signals)
    assert all(s.source == "demo:job_postings" for s in signals)


def test_funding_source_reports_amount_in_evidence():
    signals = FundingSignalSource().collect(COMPANIES)
    nimbus_signal = next(s for s in signals if s.company_id == "nimbus-voice")
    assert "42.0M" in nimbus_signal.evidence
    assert nimbus_signal.type == "funding"


def test_tech_adoption_source_matches_keywords_in_blog_snippets():
    signals = TechAdoptionSignalSource(ICP.signal_keywords["tech_adoption"]).collect(COMPANIES)
    flagged = {s.company_id for s in signals}
    assert "nimbus-voice" in flagged  # RAG pipeline mention
    assert "greencart" not in flagged  # no tech mentions at all


def test_website_change_source_uses_offline_snippet_by_default():
    signals = WebsiteChangeSignalSource(ICP.signal_keywords["website_change"], live=False).collect(COMPANIES)
    flagged = {s.company_id for s in signals}
    assert "chatterbox" in flagged
    assert "ledger-peak" not in flagged
    assert all(s.source == "demo:website_snippet" for s in signals)


def test_recency_decay_reduces_older_signal_strength():
    fresh = FundingSignalSource().collect([c for c in COMPANIES if c.id == "chatterbox"])[0]
    stale = FundingSignalSource().collect([c for c in COMPANIES if c.id == "vantage-dev"])[0]
    # chatterbox raised 30 days ago, vantage-dev 55 days ago -> chatterbox should score higher
    assert fresh.strength > stale.strength

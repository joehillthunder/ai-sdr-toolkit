from unittest.mock import patch

from sdr_toolkit.enrichment import HunterContactFinder
from sdr_toolkit.models import Company, Contact


def test_hunter_finder_unavailable_without_api_key(monkeypatch):
    monkeypatch.delenv("HUNTER_API_KEY", raising=False)
    finder = HunterContactFinder()
    assert finder.available is False
    assert finder.find_email("acme.com") is None


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_hunter_finder_returns_email_on_success():
    with patch("sdr_toolkit.enrichment.requests") as mock_requests:
        mock_requests.get.return_value = _FakeResponse({"data": {"email": "jamie@acme.com", "score": 92}})
        finder = HunterContactFinder(api_key="test-key")
        result = finder.find_email("acme.com", "Jamie Rivera")

    assert result == {"email": "jamie@acme.com", "confidence": 92}


def test_hunter_finder_returns_none_on_no_match():
    with patch("sdr_toolkit.enrichment.requests") as mock_requests:
        mock_requests.get.return_value = _FakeResponse({"data": {"email": None}})
        finder = HunterContactFinder(api_key="test-key")
        assert finder.find_email("acme.com") is None


def test_hunter_finder_survives_network_failure():
    with patch("sdr_toolkit.enrichment.requests") as mock_requests:
        mock_requests.get.side_effect = Exception("network down")
        finder = HunterContactFinder(api_key="test-key")
        assert finder.find_email("acme.com") is None


def test_enrich_contacts_only_fills_missing_emails():
    company = Company("acme", "Acme", "acme.com", "ai", 50, "SF", "desc")
    has_email = Contact("c1", "acme", "Has Email", "VP", "vp", email="already@acme.com")
    missing_email = Contact("c2", "acme", "Missing Email", "Director", "director")
    contacts_by_company = {"acme": [has_email, missing_email]}

    with patch("sdr_toolkit.enrichment.requests") as mock_requests:
        mock_requests.get.return_value = _FakeResponse({"data": {"email": "found@acme.com", "score": 80}})
        finder = HunterContactFinder(api_key="test-key")
        count = finder.enrich_contacts([company], contacts_by_company)

    assert count == 1
    assert has_email.email == "already@acme.com"  # untouched
    assert missing_email.email == "found@acme.com"


def test_enrich_contacts_noop_without_key():
    company = Company("acme", "Acme", "acme.com", "ai", 50, "SF", "desc")
    contact = Contact("c1", "acme", "No Email", "VP", "vp")
    count = HunterContactFinder(api_key=None).enrich_contacts([company], {"acme": [contact]})
    assert count == 0
    assert contact.email is None

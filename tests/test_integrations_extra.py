from unittest.mock import patch

import pytest

from sdr_toolkit.integrations import MondayAdapter, SalesforceAdapter, ZohoAdapter
from sdr_toolkit.models import Company, Dossier, ProspectPackage, QualificationResult, ScoredAccount


def test_salesforce_adapter_requires_credentials(monkeypatch):
    monkeypatch.delenv("SALESFORCE_INSTANCE_URL", raising=False)
    monkeypatch.delenv("SALESFORCE_ACCESS_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="SALESFORCE"):
        SalesforceAdapter()


def test_salesforce_adapter_constructs_with_explicit_credentials():
    adapter = SalesforceAdapter(instance_url="https://org.my.salesforce.com", access_token="tok")
    assert adapter.instance_url == "https://org.my.salesforce.com"


def test_zoho_adapter_requires_access_token(monkeypatch):
    monkeypatch.delenv("ZOHO_ACCESS_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="ZOHO_ACCESS_TOKEN"):
        ZohoAdapter()


def test_zoho_adapter_defaults_api_domain():
    adapter = ZohoAdapter(access_token="tok")
    assert adapter.api_domain == "https://www.zohoapis.com"


def test_monday_adapter_requires_token_and_board_id(monkeypatch):
    monkeypatch.delenv("MONDAY_API_TOKEN", raising=False)
    monkeypatch.delenv("MONDAY_BOARD_ID", raising=False)
    with pytest.raises(RuntimeError, match="MONDAY_API_TOKEN"):
        MondayAdapter()


def test_monday_adapter_constructs_with_explicit_credentials():
    adapter = MondayAdapter(api_token="tok", board_id="12345")
    assert adapter.board_id == "12345"


class _FakeMondayResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


def test_monday_adapter_creates_item_and_update_for_qualified_only():
    company = Company("acme", "Acme AI", "acme.ai", "ai", 80, "SF", "desc")
    scored = ScoredAccount(company, icp_fit=0.9, signal_score=0.8, combined_score=0.85)
    dossier = Dossier("acme", "Great fit.", ["scaling pains"], "Lead with hiring signal.", "mock")
    qualified_pkg = ProspectPackage(scored, [], dossier, QualificationResult("acme", "qualified", "because", 0.85), {})
    nurture_pkg = ProspectPackage(scored, [], dossier, QualificationResult("acme", "nurture", "because", 0.4), {})

    with patch("sdr_toolkit.integrations.requests") as mock_requests:
        mock_requests.post.return_value = _FakeMondayResponse({"data": {"create_item": {"id": "999"}}})
        MondayAdapter(api_token="tok", board_id="123").activate([qualified_pkg, nurture_pkg])

    # one create_item + one create_update call for the qualified package only
    assert mock_requests.post.call_count == 2
    first_call_body = mock_requests.post.call_args_list[0].kwargs["json"]
    assert "create_item" in first_call_body["query"]
    assert first_call_body["variables"]["itemName"] == "Acme AI"

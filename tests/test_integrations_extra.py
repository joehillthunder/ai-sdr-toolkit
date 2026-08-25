import pytest

from sdr_toolkit.integrations import SalesforceAdapter, ZohoAdapter


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

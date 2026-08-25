from sdr_toolkit.icp_builder import build_icp, fetch_url_text
from sdr_toolkit.llm import MockLLMClient


def test_build_icp_with_mock_llm_produces_valid_config():
    icp = build_icp(
        MockLLMClient(),
        company_name="Riverside Dental Group",
        website_texts=["We help dental practices grow."],
        ideal_customer_description="Local dental practices hiring front desk staff",
    )
    assert icp.name.startswith("Riverside Dental Group")
    assert icp.target_industries
    assert icp.min_employees < icp.max_employees
    assert icp.description_keywords
    assert icp.signal_keywords["hiring_surge"]
    assert icp.signal_keywords["tech_adoption"]
    assert icp.signal_keywords["website_change"]


def test_build_icp_handles_empty_website_text():
    icp = build_icp(MockLLMClient(), "Acme", [], "")
    assert icp.target_industries  # falls back to defaults, never empty


def test_fetch_url_text_fails_gracefully_on_bad_domain():
    text = fetch_url_text("https://this-domain-does-not-exist-sdr-toolkit.invalid", timeout=2)
    assert text == ""

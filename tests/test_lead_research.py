from sdr_toolkit.config import ICPConfig
from sdr_toolkit.lead_research import suggest_candidate_companies
from sdr_toolkit.llm import MockLLMClient


def test_suggest_candidate_companies_parses_numbered_list():
    icp = ICPConfig.default()
    results = suggest_candidate_companies(MockLLMClient(), icp, count=5)

    assert len(results) == 5
    for r in results:
        assert r["name"]
        assert r["reason"]
        assert r["source"] == "ai_research"
        assert r["verified"] is False


def test_suggest_candidate_companies_respects_count():
    icp = ICPConfig.default()
    results = suggest_candidate_companies(MockLLMClient(), icp, count=2)
    assert len(results) <= 2

from unittest.mock import patch

import pytest

flask = pytest.importorskip("flask", reason="web extra not installed (pip install -e '.[web]')")

from sdr_toolkit.webapp.server import RUNS, create_app  # noqa: E402


@pytest.fixture
def client():
    app = create_app()
    app.testing = True
    with app.test_client() as c:
        yield c


@pytest.fixture(autouse=True)
def _no_live_network():
    # WebsiteChangeSignalSource(live=True) is hard-coded in the wizard's
    # generate-leads route. In tests we don't want real DNS/HTTP calls --
    # patch requests.get to fail fast, exercising the same offline
    # fallback path a sandboxed/CI network would hit anyway.
    with patch("sdr_toolkit.signals.sources.requests") as mock_requests:
        mock_requests.get.side_effect = Exception("network disabled in tests")
        yield


def test_index_serves_wizard_page(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Lead Wizard" in resp.data


def test_test_llm_ok_with_mock_provider(client):
    resp = client.post("/api/test-llm", json={"provider": "mock"})
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True


def test_test_llm_reports_error_for_missing_key(client):
    resp = client.post("/api/test-llm", json={"provider": "anthropic"})
    data = resp.get_json()
    assert data["ok"] is False
    assert "ANTHROPIC_API_KEY" in data["error"]


def test_build_icp_returns_valid_config(client):
    resp = client.post(
        "/api/build-icp",
        json={
            "llm": {"provider": "mock"},
            "company_name": "Riverside Dental Group",
            "website_urls": [],
            "description": "Local dental practices hiring front desk staff",
        },
    )
    data = resp.get_json()
    assert resp.status_code == 200
    assert data["icp"]["target_industries"]
    assert data["icp"]["min_employees"] < data["icp"]["max_employees"]


def test_generate_leads_uses_sample_data_when_no_csv_given(client):
    icp_resp = client.post(
        "/api/build-icp",
        json={"llm": {"provider": "mock"}, "company_name": "Acme", "website_urls": [], "description": "AI startups"},
    )
    icp = icp_resp.get_json()["icp"]

    resp = client.post(
        "/api/generate-leads",
        json={"llm": {"provider": "mock"}, "icp": icp, "accounts_csv": ""},
    )
    data = resp.get_json()
    assert resp.status_code == 200
    assert data["used_sample_data"] is True
    assert len(data["packages"]) == 8
    assert data["run_id"] in RUNS
    scores = [p["combined_score"] for p in data["packages"]]
    assert scores == sorted(scores, reverse=True)


def test_generate_leads_with_custom_csv(client):
    icp_resp = client.post(
        "/api/build-icp",
        json={"llm": {"provider": "mock"}, "company_name": "Acme", "website_urls": [], "description": "AI startups"},
    )
    icp = icp_resp.get_json()["icp"]

    csv_text = (
        "company_name,domain,industry,employee_count,description,contact_name,contact_title\n"
        "Test Robotics Co,testrobotics.example,robotics,60,Builds warehouse robots,Sam Lee,VP Eng\n"
    )
    resp = client.post(
        "/api/generate-leads",
        json={"llm": {"provider": "mock"}, "icp": icp, "accounts_csv": csv_text},
    )
    data = resp.get_json()
    assert data["used_sample_data"] is False
    assert len(data["packages"]) == 1
    assert data["packages"][0]["company"]["name"] == "Test Robotics Co"
    assert data["packages"][0]["contacts"][0]["name"] == "Sam Lee"


def test_generate_leads_csv_carries_contact_linkedin_url(client):
    icp_resp = client.post(
        "/api/build-icp",
        json={"llm": {"provider": "mock"}, "company_name": "Acme", "website_urls": [], "description": "AI startups"},
    )
    icp = icp_resp.get_json()["icp"]

    csv_text = (
        "company_name,domain,contact_name,contact_title,contact_linkedin\n"
        "Test Robotics Co,testrobotics.example,Sam Lee,VP Eng,linkedin.com/in/samlee\n"
    )
    resp = client.post(
        "/api/generate-leads",
        json={"llm": {"provider": "mock"}, "icp": icp, "accounts_csv": csv_text},
    )
    data = resp.get_json()
    assert data["packages"][0]["contacts"][0]["linkedin_url"] == "linkedin.com/in/samlee"


def test_export_csv_download(client):
    icp_resp = client.post(
        "/api/build-icp",
        json={"llm": {"provider": "mock"}, "company_name": "Acme", "website_urls": [], "description": "AI startups"},
    )
    icp = icp_resp.get_json()["icp"]
    leads_resp = client.post(
        "/api/generate-leads", json={"llm": {"provider": "mock"}, "icp": icp, "accounts_csv": ""}
    )
    run_id = leads_resp.get_json()["run_id"]

    resp = client.post("/api/export", json={"run_id": run_id, "edits": {}, "crm": {"provider": "csv"}})
    assert resp.status_code == 200
    assert b"combined_score" in resp.data


def test_export_builtin_crm(client, tmp_path):
    icp_resp = client.post(
        "/api/build-icp",
        json={"llm": {"provider": "mock"}, "company_name": "Acme", "website_urls": [], "description": "AI startups"},
    )
    icp = icp_resp.get_json()["icp"]
    leads_resp = client.post(
        "/api/generate-leads", json={"llm": {"provider": "mock"}, "icp": icp, "accounts_csv": ""}
    )
    run_id = leads_resp.get_json()["run_id"]

    db_path = str(tmp_path / "crm.db")
    resp = client.post(
        "/api/export",
        json={"run_id": run_id, "edits": {}, "crm": {"provider": "builtin", "db_path": db_path}},
    )
    data = resp.get_json()
    assert data["ok"] is True
    assert data["exported"] >= 1


def test_export_unknown_run_id_returns_404(client):
    resp = client.post("/api/export", json={"run_id": "does-not-exist", "edits": {}, "crm": {"provider": "csv"}})
    assert resp.status_code == 404


def test_export_applies_sdr_edits(client):
    icp_resp = client.post(
        "/api/build-icp",
        json={"llm": {"provider": "mock"}, "company_name": "Acme", "website_urls": [], "description": "AI startups"},
    )
    icp = icp_resp.get_json()["icp"]
    leads_resp = client.post(
        "/api/generate-leads", json={"llm": {"provider": "mock"}, "icp": icp, "accounts_csv": ""}
    )
    leads = leads_resp.get_json()
    run_id = leads["run_id"]

    contact_id = None
    for pkg in leads["packages"]:
        if pkg["sequences"]:
            contact_id = next(iter(pkg["sequences"]))
            break
    assert contact_id, "expected at least one drafted sequence in sample data"

    resp = client.post(
        "/api/export",
        json={
            "run_id": run_id,
            "edits": {contact_id: {"0": {"subject": "EDITED BY SDR", "body": "edited body"}}},
            "crm": {"provider": "csv"},
        },
    )
    assert b"EDITED BY SDR" in resp.data


def test_research_leads_returns_ai_suggested_companies(client):
    icp_resp = client.post(
        "/api/build-icp",
        json={"llm": {"provider": "mock"}, "company_name": "Acme", "website_urls": [], "description": "AI startups"},
    )
    icp = icp_resp.get_json()["icp"]

    resp = client.post("/api/research-leads", json={"llm": {"provider": "mock"}, "icp": icp, "count": 4})
    data = resp.get_json()
    assert resp.status_code == 200
    assert len(data["companies"]) == 4
    assert all(c["verified"] is False for c in data["companies"])


def test_generate_leads_includes_researched_companies(client):
    icp_resp = client.post(
        "/api/build-icp",
        json={"llm": {"provider": "mock"}, "company_name": "Acme", "website_urls": [], "description": "AI startups"},
    )
    icp = icp_resp.get_json()["icp"]

    resp = client.post(
        "/api/generate-leads",
        json={
            "llm": {"provider": "mock"},
            "icp": icp,
            "accounts_csv": "",
            "manual_companies": [{"name": "Research Pick Co", "reason": "AI suggested it"}],
        },
    )
    data = resp.get_json()
    assert data["used_sample_data"] is False
    names = [p["company"]["name"] for p in data["packages"]]
    assert "Research Pick Co" in names


def test_draft_touch_appends_channel_native_message(client):
    icp_resp = client.post(
        "/api/build-icp",
        json={"llm": {"provider": "mock"}, "company_name": "Acme", "website_urls": [], "description": "AI startups"},
    )
    icp = icp_resp.get_json()["icp"]
    leads_resp = client.post(
        "/api/generate-leads", json={"llm": {"provider": "mock"}, "icp": icp, "accounts_csv": ""}
    )
    leads = leads_resp.get_json()
    run_id = leads["run_id"]

    contact_id = None
    for pkg in leads["packages"]:
        if pkg["dossier"]:
            contact_id = pkg["contacts"][0]["id"]
            break
    assert contact_id, "expected at least one account with a dossier in sample data"

    resp = client.post(
        "/api/draft-touch",
        json={"run_id": run_id, "contact_id": contact_id, "channel": "linkedin_connection_note", "llm": {"provider": "mock"}},
    )
    data = resp.get_json()
    assert resp.status_code == 200
    assert data["touch"]["channel"] == "linkedin_connection_note"
    assert data["touch"]["body"]


def test_draft_touch_unknown_contact_returns_404(client):
    icp_resp = client.post(
        "/api/build-icp",
        json={"llm": {"provider": "mock"}, "company_name": "Acme", "website_urls": [], "description": "AI startups"},
    )
    icp = icp_resp.get_json()["icp"]
    leads_resp = client.post(
        "/api/generate-leads", json={"llm": {"provider": "mock"}, "icp": icp, "accounts_csv": ""}
    )
    run_id = leads_resp.get_json()["run_id"]

    resp = client.post(
        "/api/draft-touch",
        json={"run_id": run_id, "contact_id": "no-such-contact", "channel": "x_dm", "llm": {"provider": "mock"}},
    )
    assert resp.status_code == 404


def _generate_sample_run(client):
    icp_resp = client.post(
        "/api/build-icp",
        json={"llm": {"provider": "mock"}, "company_name": "Acme", "website_urls": [], "description": "AI startups"},
    )
    icp = icp_resp.get_json()["icp"]
    leads_resp = client.post("/api/generate-leads", json={"llm": {"provider": "mock"}, "icp": icp, "accounts_csv": ""})
    return icp, leads_resp.get_json()


def test_add_company_scores_and_appends_to_run(client):
    icp, leads = _generate_sample_run(client)
    run_id = leads["run_id"]
    before = len(leads["packages"])

    resp = client.post(
        "/api/add-company",
        json={
            "run_id": run_id, "icp": icp, "llm": {"provider": "mock"},
            "company": {"name": "Added Robotics Co", "domain": "addedrobotics.example", "industry": "robotics"},
        },
    )
    data = resp.get_json()
    assert resp.status_code == 200
    assert data["package"]["company"]["name"] == "Added Robotics Co"

    # confirm it actually landed in the stored run (affects export)
    export_resp = client.post("/api/export", json={"run_id": run_id, "edits": {}, "crm": {"provider": "csv"}})
    assert b"Added Robotics Co" in export_resp.data
    assert len(RUNS[run_id].packages) == before + 1


def test_add_company_with_contact_linkedin_url(client):
    icp, leads = _generate_sample_run(client)
    resp = client.post(
        "/api/add-company",
        json={
            "run_id": leads["run_id"], "icp": icp, "llm": {"provider": "mock"},
            "company": {"name": "Added Robotics Co"},
            "contact": {"name": "Sam Lee", "title": "VP Eng", "linkedin_url": "linkedin.com/in/samlee"},
        },
    )
    data = resp.get_json()
    contact = data["package"]["contacts"][0]
    assert contact["name"] == "Sam Lee"
    assert contact["linkedin_url"] == "linkedin.com/in/samlee"


def test_add_company_requires_a_name(client):
    icp, leads = _generate_sample_run(client)
    resp = client.post(
        "/api/add-company",
        json={"run_id": leads["run_id"], "icp": icp, "llm": {"provider": "mock"}, "company": {"name": ""}},
    )
    assert resp.status_code == 400


def test_add_company_unknown_run_returns_404(client):
    resp = client.post(
        "/api/add-company",
        json={"run_id": "nope", "icp": {}, "llm": {"provider": "mock"}, "company": {"name": "X"}},
    )
    assert resp.status_code == 404


def test_remove_lead_excludes_company_from_run(client):
    icp, leads = _generate_sample_run(client)
    run_id = leads["run_id"]
    before = len(leads["packages"])
    company_id = leads["packages"][0]["company"]["id"]
    company_name = leads["packages"][0]["company"]["name"]

    resp = client.post("/api/remove-lead", json={"run_id": run_id, "company_id": company_id})
    assert resp.status_code == 200
    assert len(RUNS[run_id].packages) == before - 1

    export_resp = client.post("/api/export", json={"run_id": run_id, "edits": {}, "crm": {"provider": "csv"}})
    assert company_name.encode() not in export_resp.data


def test_remove_lead_unknown_company_returns_404(client):
    _, leads = _generate_sample_run(client)
    resp = client.post("/api/remove-lead", json={"run_id": leads["run_id"], "company_id": "no-such-id"})
    assert resp.status_code == 404

import csv

from sdr_toolkit.cli import main


def test_demo_command_runs_offline_and_exits_zero(capsys):
    exit_code = main(["demo"])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "mode: offline (mock LLM)" in out
    assert "Funnel" in out
    assert "Estimated output multiplier" in out


def test_prospect_command_with_custom_icp(capsys):
    exit_code = main(["prospect", "--icp", "examples/icp.yaml", "--limit", "3"])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "AI / Voice / Gaming ICP" in out


def test_prospect_command_exports_csv(tmp_path, capsys):
    out_path = tmp_path / "queue.csv"
    exit_code = main(["prospect", "--export", str(out_path)])
    capsys.readouterr()
    assert exit_code == 0
    assert out_path.exists()

    with out_path.open() as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 8  # all bundled demo companies
    assert {"company", "combined_score", "verdict"}.issubset(rows[0].keys())


def test_crm_list_on_empty_db_reports_nothing_saved(tmp_path, capsys):
    db_path = tmp_path / "empty.db"
    exit_code = main(["crm", "list", "--db", str(db_path)])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "No accounts saved yet" in out


def test_crm_list_shows_saved_accounts(tmp_path, capsys):
    from sdr_toolkit.simple_crm import SimpleCRMAdapter
    from sdr_toolkit.models import Company, ProspectPackage, ScoredAccount

    db_path = tmp_path / "crm.db"
    company = Company("acme", "Acme AI", "acme.ai", "ai", 80, "SF", "desc")
    scored = ScoredAccount(company, icp_fit=0.9, signal_score=0.8, combined_score=0.85)
    SimpleCRMAdapter(db_path).activate([ProspectPackage(scored, [], None, None, {})])

    exit_code = main(["crm", "list", "--db", str(db_path)])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "Acme AI" in out

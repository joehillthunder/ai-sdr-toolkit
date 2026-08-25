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

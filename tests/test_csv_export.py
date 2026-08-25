import csv
from datetime import date

from sdr_toolkit.integrations import CsvExportAdapter
from sdr_toolkit.models import (
    Company,
    Contact,
    Dossier,
    OutreachSequence,
    OutreachTouch,
    ProspectPackage,
    QualificationResult,
    ScoredAccount,
    Signal,
)

COMPANY = Company("acme", "Acme AI", "acme.ai", "ai", 80, "SF", "desc")
CONTACT = Contact(
    "acme-c1", "acme", "Jamie Rivera", "VP Eng", "vp",
    email="jamie@acme.ai", linkedin_url="linkedin.com/in/jamierivera",
)


def _package():
    scored = ScoredAccount(
        COMPANY, icp_fit=0.9, signal_score=0.8, combined_score=0.85,
        signals=[Signal("s1", "acme", "hiring_surge", 0.9, date(2026, 8, 1), "3 open roles", "test")],
    )
    dossier = Dossier("acme", "Great fit.", ["scaling pains"], "Lead with hiring signal.", "mock")
    qualification = QualificationResult("acme", "qualified", "because", 0.85)
    sequences = {CONTACT.id: OutreachSequence(CONTACT.id, [OutreachTouch("email", 0, "Hi", "Body one")])}
    return ProspectPackage(scored, [CONTACT], dossier, qualification, sequences)


def test_csv_export_includes_contact_linkedin_url(tmp_path):
    out_path = tmp_path / "queue.csv"
    CsvExportAdapter(out_path).activate([_package()])

    with out_path.open() as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 1
    assert rows[0]["first_contact"] == "Jamie Rivera"
    assert rows[0]["first_contact_title"] == "VP Eng"
    assert rows[0]["first_contact_linkedin"] == "linkedin.com/in/jamierivera"


def test_csv_export_blank_linkedin_when_no_contact(tmp_path):
    scored = ScoredAccount(COMPANY, icp_fit=0.5, signal_score=0.5, combined_score=0.5)
    package = ProspectPackage(scored, [], None, None, {})
    out_path = tmp_path / "queue.csv"
    CsvExportAdapter(out_path).activate([package])

    with out_path.open() as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["first_contact_linkedin"] == ""

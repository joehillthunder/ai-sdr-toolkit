from datetime import date

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
from sdr_toolkit.simple_crm import SimpleCRMAdapter, list_accounts

COMPANY = Company("acme", "Acme AI", "acme.ai", "ai", 80, "SF", "desc")
CONTACT = Contact(
    "acme-c1", "acme", "Jamie Rivera", "VP Eng", "vp",
    email="jamie@acme.ai", linkedin_url="linkedin.com/in/jamierivera",
)


def _package(verdict="qualified", with_sequence=True):
    scored = ScoredAccount(
        COMPANY, icp_fit=0.9, signal_score=0.8, combined_score=0.85,
        signals=[Signal("s1", "acme", "hiring_surge", 0.9, date(2026, 8, 1), "3 open roles", "test")],
    )
    dossier = Dossier("acme", "Great fit.", ["scaling pains"], "Lead with hiring signal.", "mock")
    qualification = QualificationResult("acme", verdict, "because", 0.85) if verdict else None
    sequences = {}
    if with_sequence:
        sequences[CONTACT.id] = OutreachSequence(
            CONTACT.id, [OutreachTouch("email", 0, "Hi", "Body one")]
        )
    return ProspectPackage(scored, [CONTACT], dossier, qualification, sequences)


def test_simple_crm_saves_and_lists_accounts(tmp_path):
    db_path = tmp_path / "crm.db"
    SimpleCRMAdapter(db_path).activate([_package()])

    accounts = list_accounts(db_path)
    assert len(accounts) == 1
    assert accounts[0]["name"] == "Acme AI"
    assert accounts[0]["verdict"] == "qualified"


def test_simple_crm_logs_every_account_not_just_qualified(tmp_path):
    db_path = tmp_path / "crm.db"
    SimpleCRMAdapter(db_path).activate([_package(verdict=None, with_sequence=False)])

    accounts = list_accounts(db_path)
    assert len(accounts) == 1
    assert accounts[0]["verdict"] == "below_threshold"


def test_simple_crm_upsert_updates_existing_account(tmp_path):
    db_path = tmp_path / "crm.db"
    adapter = SimpleCRMAdapter(db_path)
    adapter.activate([_package(verdict="nurture")])
    adapter.activate([_package(verdict="qualified")])

    accounts = list_accounts(db_path)
    assert len(accounts) == 1  # upserted, not duplicated
    assert accounts[0]["verdict"] == "qualified"


def test_simple_crm_saves_sequence_touches(tmp_path):
    import sqlite3

    db_path = tmp_path / "crm.db"
    SimpleCRMAdapter(db_path).activate([_package()])

    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT subject, body FROM sequence_touches").fetchall()
    conn.close()
    assert rows == [("Hi", "Body one")]


def test_simple_crm_saves_contact_linkedin_url(tmp_path):
    import sqlite3

    db_path = tmp_path / "crm.db"
    SimpleCRMAdapter(db_path).activate([_package()])

    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT linkedin_url FROM contacts WHERE id = ?", (CONTACT.id,)).fetchone()
    conn.close()
    assert row == ("linkedin.com/in/jamierivera",)

"""The "I don't have a real CRM yet" option.

A lot of small teams track leads in a spreadsheet, a Notion table, or a
weekend side-project someone vibe-coded — not Salesforce. This is a
proper, if minimal, version of that: a local SQLite file, zero setup,
zero credentials. It implements the same `ActivationAdapter` interface as
HubSpot/Salesforce/Zoho/monday.com, so it's a drop-in choice in the CRM step of the
wizard, and something a team can migrate off of later without touching
the rest of the pipeline.

Unlike the paid-CRM adapters (which only push `qualified` accounts, to
keep a real rep's CRM clean), this logs every scored account — for a team
using this as their only system of record, a `below_threshold` account is
still useful to know about, not noise to keep out.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .integrations import ActivationAdapter
from .models import ProspectPackage

DEFAULT_DB_PATH = "sdr_toolkit_crm.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    domain TEXT,
    industry TEXT,
    employee_count INTEGER,
    combined_score REAL,
    icp_fit REAL,
    signal_score REAL,
    verdict TEXT,
    dossier_summary TEXT,
    recommended_angle TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS contacts (
    id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL REFERENCES accounts(id),
    name TEXT,
    title TEXT,
    email TEXT,
    linkedin_url TEXT
);

CREATE TABLE IF NOT EXISTS sequence_touches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_id TEXT NOT NULL REFERENCES contacts(id),
    account_id TEXT NOT NULL REFERENCES accounts(id),
    touch_index INTEGER NOT NULL,
    channel TEXT,
    day_offset INTEGER,
    subject TEXT,
    body TEXT,
    status TEXT DEFAULT 'draft'
);
"""


def _connect(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(_SCHEMA)
    return conn


class SimpleCRMAdapter(ActivationAdapter):
    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH):
        self.db_path = db_path

    def activate(self, packages: list[ProspectPackage]) -> None:
        conn = _connect(self.db_path)
        try:
            with conn:
                for pkg in packages:
                    self._upsert_account(conn, pkg)
        finally:
            conn.close()

    def _upsert_account(self, conn: sqlite3.Connection, pkg: ProspectPackage) -> None:
        sa = pkg.scored_account
        conn.execute(
            """INSERT INTO accounts
               (id, name, domain, industry, employee_count, combined_score,
                icp_fit, signal_score, verdict, dossier_summary, recommended_angle, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(id) DO UPDATE SET
                 combined_score=excluded.combined_score, icp_fit=excluded.icp_fit,
                 signal_score=excluded.signal_score, verdict=excluded.verdict,
                 dossier_summary=excluded.dossier_summary,
                 recommended_angle=excluded.recommended_angle,
                 updated_at=CURRENT_TIMESTAMP""",
            (
                sa.company.id,
                sa.company.name,
                sa.company.domain,
                sa.company.industry,
                sa.company.employee_count,
                sa.combined_score,
                sa.icp_fit,
                sa.signal_score,
                pkg.qualification.verdict if pkg.qualification else "below_threshold",
                pkg.dossier.summary if pkg.dossier else None,
                pkg.dossier.recommended_angle if pkg.dossier else None,
            ),
        )
        for contact in pkg.contacts:
            conn.execute(
                """INSERT INTO contacts (id, account_id, name, title, email, linkedin_url)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET name=excluded.name, title=excluded.title,
                     email=excluded.email, linkedin_url=excluded.linkedin_url""",
                (contact.id, sa.company.id, contact.name, contact.title, contact.email, contact.linkedin_url),
            )
            sequence = pkg.sequences.get(contact.id)
            if not sequence:
                continue
            conn.execute(
                "DELETE FROM sequence_touches WHERE contact_id = ?", (contact.id,)
            )
            for i, touch in enumerate(sequence.touches):
                conn.execute(
                    """INSERT INTO sequence_touches
                       (contact_id, account_id, touch_index, channel, day_offset, subject, body)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (contact.id, sa.company.id, i, touch.channel, touch.day_offset, touch.subject, touch.body),
                )


def list_accounts(db_path: str | Path = DEFAULT_DB_PATH) -> list[dict]:
    """Read helper for a CLI/UI to show what's already been saved."""
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM accounts ORDER BY combined_score DESC"
        ).fetchall()
        cols = [c[0] for c in conn.execute("SELECT * FROM accounts LIMIT 0").description]
        return [dict(zip(cols, row)) for row in rows]
    finally:
        conn.close()

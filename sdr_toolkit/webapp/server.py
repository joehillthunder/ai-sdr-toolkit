"""Flask backend for the wizard.

Three screens, three real jobs:
  1. Connect your AI + your CRM (credentials never touch disk here).
  2. Describe your business -> we propose an ICP you can edit.
  3. Generate a scored, prioritized lead list with drafted drip
     sequences -> review, edit, export.

State for a single generation run is kept in an in-process dict keyed by
a run_id. That's a deliberate MVP simplification: this app is meant to
run locally, for one person, for one sitting — not as a multi-user
server. Swap in a real datastore before deploying it as one.
"""

from __future__ import annotations

import csv
import dataclasses
import io
import os
import re
import uuid
from pathlib import Path

from flask import Flask, jsonify, request, send_file

from ..agents import PersonalizationAgent
from ..config import ICPConfig
from ..enrichment import HunterContactFinder
from ..icp_builder import build_icp, fetch_url_text
from ..integrations import CsvExportAdapter, HubSpotAdapter, MondayAdapter, SalesforceAdapter, ZohoAdapter
from ..lead_research import suggest_candidate_companies
from ..llm import get_client
from ..models import Company, Contact, OutreachSequence
from ..orchestrator import Pipeline
from ..signals.demo_data import demo_companies, demo_contacts
from ..signals.sources import (
    CareersPageSignalSource,
    FundingSignalSource,
    TechAdoptionSignalSource,
    WebsiteChangeSignalSource,
)
from ..simple_crm import SimpleCRMAdapter

RUNS: dict[str, object] = {}
EXPORT_DIR = Path(os.environ.get("TMPDIR", "/tmp")) / "sdr_toolkit_exports"


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/")
    def index():
        return (Path(__file__).parent / "templates" / "wizard.html").read_text()

    @app.post("/api/test-llm")
    def test_llm():
        data = request.get_json(force=True) or {}
        try:
            client = _client_from_payload(data)
            sample = client.generate("You are a connection test.", "Reply with the single word OK.")
            return jsonify(ok=True, sample=sample[:160])
        except Exception as exc:  # noqa: BLE001
            return jsonify(ok=False, error=str(exc))

    @app.post("/api/build-icp")
    def api_build_icp():
        data = request.get_json(force=True) or {}
        try:
            client = _client_from_payload(data.get("llm", {}))
        except Exception as exc:  # noqa: BLE001
            return jsonify(error=str(exc)), 400

        urls = [u.strip() for u in data.get("website_urls", []) if u.strip()]
        texts = [fetch_url_text(u) for u in urls]
        icp = build_icp(
            client,
            data.get("company_name") or "Your company",
            texts,
            data.get("description", ""),
        )
        return jsonify(icp=dataclasses.asdict(icp), fetched_sites=sum(1 for t in texts if t))

    @app.post("/api/research-leads")
    def api_research_leads():
        """The "research" lead source: ask the model to brainstorm real
        companies that plausibly fit the ICP. Explicitly unverified —
        see sdr_toolkit/lead_research.py."""
        data = request.get_json(force=True) or {}
        try:
            icp = ICPConfig(**data["icp"])
            client = _client_from_payload(data.get("llm", {}))
        except Exception as exc:  # noqa: BLE001
            return jsonify(error=str(exc)), 400

        count = int(data.get("count") or 8)
        region = data.get("region") or ""
        try:
            suggestions = suggest_candidate_companies(client, icp, count=count, region=region)
        except Exception as exc:  # noqa: BLE001
            return jsonify(error=str(exc)), 400
        return jsonify(companies=suggestions)

    @app.post("/api/generate-leads")
    def api_generate_leads():
        data = request.get_json(force=True) or {}
        try:
            icp = ICPConfig(**data["icp"])
            client = _client_from_payload(data.get("llm", {}))
        except Exception as exc:  # noqa: BLE001
            return jsonify(error=str(exc)), 400

        accounts_csv = data.get("accounts_csv") or ""
        manual_companies = data.get("manual_companies") or []
        companies, contacts_by_company = _load_accounts(accounts_csv, manual_companies)
        used_sample = not accounts_csv.strip() and not manual_companies

        hunter_key = data.get("hunter_api_key") or None
        enriched_emails = 0
        if hunter_key:
            enriched_emails = HunterContactFinder(api_key=hunter_key).enrich_contacts(
                companies, contacts_by_company
            )

        pipeline = Pipeline(icp=icp, llm_client=client, signal_sources=_default_sources(icp))
        result = pipeline.run(companies, contacts_by_company)

        run_id = uuid.uuid4().hex[:12]
        RUNS[run_id] = result

        return jsonify(
            run_id=run_id,
            used_sample_data=used_sample,
            enriched_emails=enriched_emails,
            packages=[_package_to_dict(p) for p in result.packages],
        )

    @app.post("/api/add-company")
    def api_add_company():
        """Score and (if it qualifies) draft outreach for one more company
        against a run already in progress -- lets a rep add a company the
        original ICP/CSV missed (a different industry, a competitor's
        customer, whatever) without regenerating the whole list."""
        data = request.get_json(force=True) or {}
        run_id = data.get("run_id")
        result = RUNS.get(run_id)
        if not result:
            return jsonify(error="This lead list has expired. Generate it again."), 404

        try:
            icp = ICPConfig(**data["icp"])
            client = _client_from_payload(data.get("llm", {}))
        except Exception as exc:  # noqa: BLE001
            return jsonify(error=str(exc)), 400

        company_data = data.get("company") or {}
        name = (company_data.get("name") or "").strip()
        if not name:
            return jsonify(error="A company name is required."), 400

        existing_ids = {p.scored_account.company.id for p in result.packages}
        company_id = _unique_id(_slugify(name, "added"), existing_ids)
        domain = (company_data.get("domain") or "").strip() or f"{company_id}.example.com"
        company = Company(
            id=company_id,
            name=name,
            domain=domain,
            industry=(company_data.get("industry") or "").strip(),
            employee_count=int(company_data.get("employee_count") or 0) if str(company_data.get("employee_count") or "").isdigit() else 0,
            headquarters=(company_data.get("headquarters") or "").strip(),
            description=(company_data.get("description") or "").strip(),
        )
        contact = Contact(
            id=f"{company_id}-c1", company_id=company_id, name="Decision Maker", title="Leadership", seniority="unknown",
        )

        pipeline = Pipeline(icp=icp, llm_client=client, signal_sources=_default_sources(icp))
        one_off = pipeline.run([company], {company_id: [contact]})
        new_package = one_off.packages[0]

        result.packages.append(new_package)
        result.packages.sort(key=lambda p: p.scored_account.combined_score, reverse=True)

        return jsonify(package=_package_to_dict(new_package))

    @app.post("/api/remove-lead")
    def api_remove_lead():
        """Drop one company from a run in progress -- it's excluded from
        every subsequent export/draft-touch call for that run_id."""
        data = request.get_json(force=True) or {}
        run_id = data.get("run_id")
        result = RUNS.get(run_id)
        if not result:
            return jsonify(error="This lead list has expired. Generate it again."), 404

        company_id = data.get("company_id")
        before = len(result.packages)
        result.packages = [p for p in result.packages if p.scored_account.company.id != company_id]
        if len(result.packages) == before:
            return jsonify(error="Unknown company for this run."), 404
        return jsonify(ok=True)

    @app.post("/api/draft-touch")
    def api_draft_touch():
        """Draft one additional channel-native touch (LinkedIn connection
        note, X DM, Instagram DM) for a contact already in a run. Additive
        to whatever sequence that contact already has -- never sent, only
        drafted, same as everything else here."""
        data = request.get_json(force=True) or {}
        run_id = data.get("run_id")
        result = RUNS.get(run_id)
        if not result:
            return jsonify(error="This lead list has expired. Generate it again."), 404

        contact_id = data.get("contact_id")
        channel = data.get("channel")

        pkg = next((p for p in result.packages if any(c.id == contact_id for c in p.contacts)), None)
        if not pkg:
            return jsonify(error="Unknown contact for this run."), 404
        if not pkg.dossier:
            return jsonify(error="This account is below the nurture bar and has no dossier to draft from."), 400
        contact = next(c for c in pkg.contacts if c.id == contact_id)

        try:
            client = _client_from_payload(data.get("llm", {}))
            touch = PersonalizationAgent(client).draft_channel_touch(
                pkg.scored_account.company, contact, pkg.dossier, pkg.scored_account.signals, channel
            )
        except Exception as exc:  # noqa: BLE001
            return jsonify(error=str(exc)), 400

        seq = pkg.sequences.get(contact_id)
        if seq is None:
            seq = OutreachSequence(contact_id=contact_id, touches=[])
            pkg.sequences[contact_id] = seq
        seq.touches.append(touch)

        return jsonify(touch=dataclasses.asdict(touch), touch_index=len(seq.touches) - 1)

    @app.post("/api/export")
    def api_export():
        data = request.get_json(force=True) or {}
        run_id = data.get("run_id")
        result = RUNS.get(run_id)
        if not result:
            return jsonify(error="This lead list has expired. Generate it again."), 404

        _apply_edits(result.packages, data.get("edits") or {})

        crm = data.get("crm") or {}
        provider = (crm.get("provider") or "csv").lower()

        try:
            if provider == "csv":
                EXPORT_DIR.mkdir(parents=True, exist_ok=True)
                path = EXPORT_DIR / f"{run_id}.csv"
                CsvExportAdapter(path).activate(result.packages)
                return send_file(path, as_attachment=True, download_name="lead_queue.csv")
            if provider == "hubspot":
                HubSpotAdapter(access_token=crm.get("access_token")).activate(result.packages)
            elif provider == "salesforce":
                SalesforceAdapter(
                    instance_url=crm.get("instance_url"), access_token=crm.get("access_token")
                ).activate(result.packages)
            elif provider == "zoho":
                ZohoAdapter(
                    access_token=crm.get("access_token"), api_domain=crm.get("api_domain")
                ).activate(result.packages)
            elif provider == "monday":
                MondayAdapter(
                    api_token=crm.get("access_token"), board_id=crm.get("board_id")
                ).activate(result.packages)
            elif provider == "builtin":
                SimpleCRMAdapter(crm.get("db_path") or "sdr_toolkit_crm.db").activate(result.packages)
            else:
                return jsonify(error=f"Unknown CRM provider: {provider}"), 400
        except Exception as exc:  # noqa: BLE001
            return jsonify(error=str(exc)), 400

        qualified = sum(1 for p in result.packages if p.qualification and p.qualification.verdict == "qualified")
        return jsonify(ok=True, exported=qualified)

    return app


# ---------------------------------------------------------------- helpers

def _default_sources(icp: ICPConfig) -> list:
    return [
        CareersPageSignalSource(icp.signal_keywords.get("hiring_surge", [])),
        WebsiteChangeSignalSource(icp.signal_keywords.get("website_change", []), live=True),
        FundingSignalSource(),
        TechAdoptionSignalSource(icp.signal_keywords.get("tech_adoption", [])),
    ]


def _client_from_payload(payload: dict):
    return get_client(
        provider=payload.get("provider", "mock"),
        model=payload.get("model") or None,
        api_key=payload.get("api_key") or None,
        base_url=payload.get("base_url") or None,
    )


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(text: str, fallback: str) -> str:
    slug = _SLUG_RE.sub("-", (text or "").lower()).strip("-")
    return slug or fallback


def _load_accounts(
    accounts_csv: str, manual_companies: list[dict] | None = None
) -> tuple[list[Company], dict[str, list[Contact]]]:
    manual_companies = manual_companies or []

    if not accounts_csv.strip() and not manual_companies:
        companies = demo_companies()
        contacts_by_company: dict[str, list[Contact]] = {}
        for c in demo_contacts():
            contacts_by_company.setdefault(c.company_id, []).append(c)
        return companies, contacts_by_company

    companies = []
    contacts_by_company = {}
    used_ids: set[str] = set()

    if accounts_csv.strip():
        reader = csv.DictReader(io.StringIO(accounts_csv))
        for i, row in enumerate(reader):
            name = (row.get("company_name") or row.get("name") or "").strip()
            if not name:
                continue
            company_id = _unique_id(_slugify(name, f"account-{i}"), used_ids)
            domain = (row.get("domain") or "").strip() or f"{company_id}.example.com"
            companies.append(
                Company(
                    id=company_id,
                    name=name,
                    domain=domain,
                    industry=(row.get("industry") or "").strip(),
                    employee_count=int(row.get("employee_count") or 0)
                    if str(row.get("employee_count") or "").strip().isdigit()
                    else 0,
                    headquarters=(row.get("headquarters") or "").strip(),
                    description=(row.get("description") or "").strip(),
                )
            )
            contact_name = (row.get("contact_name") or "").strip() or "Decision Maker"
            contacts_by_company[company_id] = [
                Contact(
                    id=f"{company_id}-c1",
                    company_id=company_id,
                    name=contact_name,
                    title=(row.get("contact_title") or "").strip() or "Leadership",
                    seniority="unknown",
                    email=(row.get("contact_email") or "").strip() or None,
                    twitter_handle=(row.get("contact_twitter") or "").strip() or None,
                    instagram_handle=(row.get("contact_instagram") or "").strip() or None,
                )
            ]

    # "Research" lead source: AI-suggested candidates, always with a
    # placeholder domain (no real URL to check) -- see lead_research.py.
    for i, mc in enumerate(manual_companies):
        name = (mc.get("name") or "").strip()
        if not name:
            continue
        company_id = _unique_id(_slugify(name, f"research-{i}"), used_ids)
        companies.append(
            Company(
                id=company_id,
                name=name,
                domain=f"{company_id}.example.com",
                industry="",
                employee_count=0,
                headquarters="",
                description=(mc.get("reason") or "AI-suggested candidate — verify before outreach."),
            )
        )
        contacts_by_company[company_id] = [
            Contact(
                id=f"{company_id}-c1",
                company_id=company_id,
                name="Decision Maker",
                title="Leadership",
                seniority="unknown",
            )
        ]

    return companies, contacts_by_company


def _unique_id(candidate: str, used_ids: set[str]) -> str:
    company_id = candidate
    n = 2
    while company_id in used_ids:
        company_id = f"{candidate}-{n}"
        n += 1
    used_ids.add(company_id)
    return company_id


def _package_to_dict(pkg) -> dict:
    sa = pkg.scored_account
    return {
        "company": dataclasses.asdict(sa.company),
        "icp_fit": sa.icp_fit,
        "signal_score": sa.signal_score,
        "combined_score": sa.combined_score,
        "signals": [
            {"type": s.type, "strength": s.strength, "evidence": s.evidence, "source": s.source}
            for s in sa.signals
        ],
        "verdict": pkg.qualification.verdict if pkg.qualification else "below_threshold",
        "rationale": pkg.qualification.rationale if pkg.qualification else None,
        "dossier": dataclasses.asdict(pkg.dossier) if pkg.dossier else None,
        "contacts": [dataclasses.asdict(c) for c in pkg.contacts],
        "sequences": {
            contact_id: [dataclasses.asdict(t) for t in seq.touches]
            for contact_id, seq in pkg.sequences.items()
        },
    }


def _apply_edits(packages, edits: dict) -> None:
    """edits shape: {contact_id: {touch_index (str): {subject, body}}}"""
    by_contact = {}
    for pkg in packages:
        for contact_id, seq in pkg.sequences.items():
            by_contact[contact_id] = seq

    for contact_id, touch_edits in edits.items():
        seq = by_contact.get(contact_id)
        if not seq:
            continue
        for idx_str, values in touch_edits.items():
            try:
                idx = int(idx_str)
            except ValueError:
                continue
            if idx < 0 or idx >= len(seq.touches):
                continue
            touch = seq.touches[idx]
            if "subject" in values:
                touch.subject = values["subject"]
            if "body" in values:
                touch.body = values["body"]

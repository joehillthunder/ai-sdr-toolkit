"""Command-line entrypoint.

    sdr-toolkit demo                     # zero-config, offline, runs in ~instantly
    sdr-toolkit prospect --icp examples/icp.yaml --limit 5 --live
    sdr-toolkit prospect --export out/queue.csv
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict

from .config import ICPConfig
from .integrations import CsvExportAdapter
from .llm import get_client
from .models import Company, Contact
from .orchestrator import Pipeline
from .reporting import build_funnel_metrics
from .signals.demo_data import demo_companies, demo_contacts
from .signals.sources import (
    FundingSignalSource,
    HiringSurgeSignalSource,
    TechAdoptionSignalSource,
    WebsiteChangeSignalSource,
)


def _contacts_by_company(contacts: list[Contact]) -> dict[str, list[Contact]]:
    by_company: dict[str, list[Contact]] = defaultdict(list)
    for c in contacts:
        by_company[c.company_id].append(c)
    return dict(by_company)


def _build_sources(icp: ICPConfig, live: bool) -> list:
    return [
        HiringSurgeSignalSource(icp.signal_keywords.get("hiring_surge", []), live=live),
        FundingSignalSource(),
        TechAdoptionSignalSource(icp.signal_keywords.get("tech_adoption", [])),
        WebsiteChangeSignalSource(icp.signal_keywords.get("website_change", []), live=live),
    ]


def _print_queue(result, top_n: int = 25) -> None:
    print(f"\n{'SCORE':>6}  {'FIT':>5}  {'SIG':>5}  {'VERDICT':<14} COMPANY")
    print("-" * 70)
    for pkg in result.packages[:top_n]:
        sa = pkg.scored_account
        verdict = pkg.qualification.verdict if pkg.qualification else "below_threshold"
        print(f"{sa.combined_score:>6.2f}  {sa.icp_fit:>5.2f}  {sa.signal_score:>5.2f}  {verdict:<14} {sa.company.name}")


def _print_top_detail(result) -> None:
    qualified = [p for p in result.packages if p.qualification and p.qualification.verdict == "qualified"]
    if not qualified:
        print("\nNo accounts cleared the qualification threshold in this run.")
        return
    top = qualified[0]
    print(f"\n--- Detail: {top.scored_account.company.name} ---")
    if top.dossier:
        print(f"Summary: {top.dossier.summary}")
        print(f"Pain points: {'; '.join(top.dossier.pain_points)}")
        print(f"Angle: {top.dossier.recommended_angle}")
    if top.qualification:
        print(f"Qualification: {top.qualification.verdict} — {top.qualification.rationale}")
    if top.sequences:
        first_contact_id = next(iter(top.sequences))
        seq = top.sequences[first_contact_id]
        contact = next((c for c in top.contacts if c.id == first_contact_id), None)
        print(f"\nSample sequence for {contact.name if contact else first_contact_id}:")
        for touch in seq.touches:
            label = f"[{touch.channel} +{touch.day_offset}d]"
            if touch.subject:
                print(f"  {label} Subject: {touch.subject}")
            print(f"  {label} {touch.body}")


def _print_funnel(result, signals_collected: int, live: bool) -> None:
    metrics = build_funnel_metrics(result.packages, signals_collected, result.elapsed_seconds)
    print("\n--- Funnel ---")
    print(f"Accounts considered:        {metrics.accounts_considered}")
    print(f"Signals collected:          {metrics.signals_collected}")
    print(f"Cleared nurture bar:        {metrics.accounts_nurture_or_better}")
    print(f"Qualified:                  {metrics.accounts_qualified}")
    print(f"Sequences drafted:          {metrics.sequences_drafted}")
    print(f"Pipeline wall time:         {metrics.elapsed_seconds}s")
    print(f"Manual-equivalent time:     {metrics.manual_minutes_equivalent} min")
    if live:
        print(f"Estimated output multiplier: {metrics.output_multiplier}x vs. fully manual research + drafting")
    else:
        print(
            "Estimated output multiplier: n/a (offline mock LLM calls are near-instant; "
            "re-run with --live for a timing estimate based on real model latency)"
        )


def run_pipeline(icp_path: str | None, limit: int | None, live: bool, export: str | None) -> int:
    icp = ICPConfig.from_yaml(icp_path) if icp_path else ICPConfig.default()

    try:
        llm = get_client(live=live)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    companies: list[Company] = demo_companies()
    contacts = _contacts_by_company(demo_contacts())
    sources = _build_sources(icp, live=live)

    pipeline = Pipeline(icp=icp, llm_client=llm, signal_sources=sources)
    result = pipeline.run(companies, contacts, limit=limit)

    mode = "live (Claude)" if live else "offline (mock LLM)"
    print(f"ICP: {icp.name}  |  mode: {mode}  |  accounts: {len(companies)}")
    _print_queue(result)
    _print_top_detail(result)
    _print_funnel(result, result.signals_collected, live=live)

    if export:
        CsvExportAdapter(export).activate(result.packages)
        print(f"\nExported prioritized queue to {export}")

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sdr-toolkit", description="AI SDR/BDR Toolkit -- SDR prospecting + BDR partnership discovery")
    sub = parser.add_subparsers(dest="command", required=True)

    demo_p = sub.add_parser("demo", help="Run the full pipeline on bundled sample data (zero config).")
    demo_p.add_argument("--live", action="store_true", help="Use a real Claude model (requires ANTHROPIC_API_KEY).")

    prospect_p = sub.add_parser("prospect", help="Run the pipeline with a custom ICP.")
    prospect_p.add_argument("--icp", type=str, default=None, help="Path to an ICP YAML file (see examples/icp.yaml).")
    prospect_p.add_argument("--limit", type=int, default=None, help="Only score/process the top N accounts.")
    prospect_p.add_argument("--live", action="store_true", help="Use a real Claude model (requires ANTHROPIC_API_KEY).")
    prospect_p.add_argument("--export", type=str, default=None, help="Write the prioritized queue to this CSV path.")

    wizard_p = sub.add_parser("wizard", help="Launch the browser-based lead wizard for non-technical users.")
    wizard_p.add_argument("--port", type=int, default=5055)
    wizard_p.add_argument("--no-browser", action="store_true", help="Don't auto-open a browser tab.")

    crm_p = sub.add_parser("crm", help="Inspect the built-in local CRM (sdr_toolkit.simple_crm).")
    crm_sub = crm_p.add_subparsers(dest="crm_command", required=True)
    crm_list_p = crm_sub.add_parser("list", help="List accounts saved to the built-in CRM.")
    crm_list_p.add_argument("--db", type=str, default="sdr_toolkit_crm.db")

    bd_p = sub.add_parser("bd", help="Business development: long-cycle account research & partnership discovery.")
    bd_sub = bd_p.add_subparsers(dest="bd_command", required=True)

    bd_account_p = bd_sub.add_parser("account", help="Run the 9-stage BD account research chain.")
    bd_account_p.add_argument("company")
    bd_account_p.add_argument("--product", type=str, default="", help="Your product/technology, for partnership framing.")
    bd_account_p.add_argument("--context", type=str, default="", help="Any extra context to seed the research with.")
    bd_account_p.add_argument("--live", action="store_true")
    bd_account_p.add_argument("--provider", type=str, default=None)

    bd_watch_p = bd_sub.add_parser("watch", help="Check watched companies' feeds for partnership-relevant announcements.")
    bd_watch_p.add_argument("--config", type=str, required=True, help="YAML: companies (name -> RSS url) + topics.")
    bd_watch_p.add_argument("--live", action="store_true")
    bd_watch_p.add_argument("--provider", type=str, default=None)

    bd_tech_p = bd_sub.add_parser("analyze-tech", help="Assess an SDK/API/repo/product doc for partnership fit.")
    bd_tech_p.add_argument("source", help="A URL or a local file path.")
    bd_tech_p.add_argument("--product", type=str, default="")
    bd_tech_p.add_argument("--live", action="store_true")
    bd_tech_p.add_argument("--provider", type=str, default=None)

    bd_hunt_p = bd_sub.add_parser("hunt", help="Turn a signal into a full partnership opportunity chain.")
    bd_hunt_p.add_argument("--company", type=str, default=None, help="Used with --signal for a one-off manual run.")
    bd_hunt_p.add_argument("--signal", type=str, default=None, help="Freeform description of the signal you noticed.")
    bd_hunt_p.add_argument("--config", type=str, default=None, help="Run watch first, then hunt on every signal found.")
    bd_hunt_p.add_argument("--criteria", type=str, default="", help="Your partnership criteria/ICP, freeform.")
    bd_hunt_p.add_argument("--live", action="store_true")
    bd_hunt_p.add_argument("--provider", type=str, default=None)

    args = parser.parse_args(argv)

    if args.command == "demo":
        return run_pipeline(icp_path=None, limit=None, live=args.live, export=None)
    if args.command == "prospect":
        return run_pipeline(icp_path=args.icp, limit=args.limit, live=args.live, export=args.export)
    if args.command == "wizard":
        return run_wizard(port=args.port, open_browser=not args.no_browser)
    if args.command == "crm" and args.crm_command == "list":
        return print_crm_accounts(args.db)
    if args.command == "bd":
        return run_bd_command(args)
    return 1


def run_wizard(port: int, open_browser: bool) -> int:
    try:
        from .webapp.server import create_app
    except ImportError:
        print(
            "error: the wizard needs Flask. Install it with `pip install -e '.[web]'`.",
            file=sys.stderr,
        )
        return 1

    app = create_app()
    url = f"http://127.0.0.1:{port}"
    print(f"Lead wizard running at {url}  (Ctrl+C to stop)")

    if open_browser:
        import threading
        import webbrowser

        threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)
    return 0


def print_crm_accounts(db_path: str) -> int:
    from .simple_crm import list_accounts

    accounts = list_accounts(db_path)
    if not accounts:
        print(f"No accounts saved yet in {db_path}.")
        return 0
    print(f"{'SCORE':>6}  {'VERDICT':<14} COMPANY")
    print("-" * 60)
    for a in accounts:
        print(f"{a['combined_score']:>6.2f}  {a['verdict']:<14} {a['name']}")
    return 0


# --------------------------------------------------------------- BD commands

def run_bd_command(args) -> int:
    from .bd.agents import AccountResearchAgent, PartnershipHunterAgent, TechnicalBDAnalystAgent
    from .bd.partner_feeds import watch_partners

    provider = args.provider or ("anthropic" if args.live else "mock")
    try:
        llm = get_client(provider=provider)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.bd_command == "account":
        dossier = AccountResearchAgent(llm).research(args.company, our_product=args.product, context=args.context)
        _print_bd_account(dossier)
        return 0

    if args.bd_command == "watch":
        feeds, topics = _load_watchlist(args.config)
        signals = watch_partners(llm, feeds, topics)
        _print_partner_signals(signals)
        return 0

    if args.bd_command == "analyze-tech":
        text = _read_source(args.source)
        if not text:
            print(f"error: could not read anything from {args.source!r}", file=sys.stderr)
            return 1
        assessment = TechnicalBDAnalystAgent(llm).analyze(args.source, text, our_product=args.product)
        _print_technical_assessment(assessment)
        return 0

    if args.bd_command == "hunt":
        hunter = PartnershipHunterAgent(llm)
        if args.config:
            feeds, topics = _load_watchlist(args.config)
            signals = watch_partners(llm, feeds, topics)
            if not signals:
                print("No partnership-relevant signals found in this run.")
                return 0
            for signal in signals:
                opportunity = hunter.hunt_from_signal(signal, partnership_criteria=args.criteria)
                _print_partnership_opportunity(opportunity)
            return 0
        if args.company and args.signal:
            opportunity = hunter.hunt(args.company, args.signal, partnership_criteria=args.criteria)
            _print_partnership_opportunity(opportunity)
            return 0
        print("error: pass either --config <watchlist.yaml>, or both --company and --signal.", file=sys.stderr)
        return 1

    return 1


def _read_source(source: str) -> str:
    """URL -> fetched page text; existing local path -> file contents;
    anything else -> treated as literal pasted text."""
    from pathlib import Path

    if source.startswith(("http://", "https://")):
        from .icp_builder import fetch_url_text

        return fetch_url_text(source)
    path = Path(source)
    if path.is_file():
        return path.read_text(errors="ignore")
    return source


def _load_watchlist(path: str) -> tuple[dict[str, str], list[str]]:
    import yaml

    raw = yaml.safe_load(open(path)) or {}
    return raw.get("companies", {}), raw.get("topics", [])


def _print_bd_account(d) -> None:
    print(f"\n=== BD Account Research: {d.company} ===")
    print(f"\nOrg mapping:            {d.org_mapping}")
    print(f"Product strategy:       {d.product_strategy}")
    print(f"Partnership hypothesis: {d.partnership_hypothesis}")
    print(f"Target executives:      {'; '.join(d.target_executives)}")
    print(f"Recent initiatives:     {d.recent_initiatives}")
    print(f"Competitive landscape:  {d.competitive_landscape}")
    print(f"\nPersonalized outreach angle:\n  {d.personalized_outreach}")
    print("\nMeeting prep:")
    for item in d.meeting_prep:
        print(f"  - {item}")


def _print_partner_signals(signals) -> None:
    if not signals:
        print("No partnership-relevant announcements found.")
        return
    for s in signals:
        a = s.announcement
        print(f"\n[{a.company}] {a.title}")
        if a.published_at:
            print(f"  Published: {a.published_at}")
        print(f"  Topics matched: {', '.join(s.topics_matched)}")
        print(f"  Why it matters: {s.relevance}")
        print(f"  URL: {a.url}")


def _print_technical_assessment(t) -> None:
    print(f"\n=== Technical BD Assessment: {t.source} ===")
    print(f"\nIntegration opportunity: {t.integration_opportunity}")
    print(f"Engineering effort:      {t.engineering_effort}")
    print(f"Partner pitch:           {t.partner_pitch}")


def _print_partnership_opportunity(o) -> None:
    print(f"\n=== Partnership Opportunity: {o.company} ===")
    print(f"Signal:              {o.signal}")
    print(f"Opportunity:         {o.opportunity}")
    print(f"Partner hypothesis:  {o.partner_hypothesis}")
    print(f"Target executive:    {o.target_executive}")
    print(f"Pitch:               {o.pitch}")
    print(f"Next action:         {o.next_action}")


if __name__ == "__main__":
    raise SystemExit(main())

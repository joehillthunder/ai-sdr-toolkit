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
    parser = argparse.ArgumentParser(prog="sdr-toolkit", description="AI-native SDR & BD prospecting toolkit")
    sub = parser.add_subparsers(dest="command", required=True)

    demo_p = sub.add_parser("demo", help="Run the full pipeline on bundled sample data (zero config).")
    demo_p.add_argument("--live", action="store_true", help="Use a real Claude model (requires ANTHROPIC_API_KEY).")

    prospect_p = sub.add_parser("prospect", help="Run the pipeline with a custom ICP.")
    prospect_p.add_argument("--icp", type=str, default=None, help="Path to an ICP YAML file (see examples/icp.yaml).")
    prospect_p.add_argument("--limit", type=int, default=None, help="Only score/process the top N accounts.")
    prospect_p.add_argument("--live", action="store_true", help="Use a real Claude model (requires ANTHROPIC_API_KEY).")
    prospect_p.add_argument("--export", type=str, default=None, help="Write the prioritized queue to this CSV path.")

    args = parser.parse_args(argv)

    if args.command == "demo":
        return run_pipeline(icp_path=None, limit=None, live=args.live, export=None)
    if args.command == "prospect":
        return run_pipeline(icp_path=args.icp, limit=args.limit, live=args.live, export=args.export)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

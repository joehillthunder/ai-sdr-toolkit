# ai-sdr-toolkit

An AI-native SDR & BD prospecting pipeline: signal-based scoring plus
agentic research, qualification, and personalization — built to maximize
qualified output per rep, not raw volume of AI-generated noise.

[![CI](https://github.com/joehillthunder/ai-sdr-toolkit/actions/workflows/ci.yml/badge.svg)](https://github.com/joehillthunder/ai-sdr-toolkit/actions/workflows/ci.yml)

## Why this exists

Built as a working reference implementation of what a JD for a sales
development leadership role described as designing an *"AI-native SDR
motion using agents, automation, and signal-based prospecting."* Rather
than write about how I'd approach that, this is the thing itself: a
pipeline that turns raw buying signals into a prioritized, ready-to-work
queue with drafted outreach — runnable, testable, and inspectable end to
end.

## What it does

1. **Collects signals** — hiring surges, funding events, tech-stack
   adoption, and website/product language changes — from pluggable
   sources (`sdr_toolkit/signals/`).
2. **Scores deterministically** — ICP fit + weighted, recency-decayed
   signal strength → a single combined score (`sdr_toolkit/scoring.py`).
   This step is intentionally *not* LLM-based: it's cheap, reproducible,
   and it's what gates which accounts are worth spending a model call on
   at all.
3. **Runs agents only on accounts that clear the bar** — a
   `ResearchAgent` builds an account dossier, a `QualificationAgent`
   explains the verdict, and a `PersonalizationAgent` drafts a 3-touch,
   signal-referencing outreach sequence (`sdr_toolkit/agents.py`).
4. **Activates the output** — exports a prioritized, rep-ready queue to
   CSV, or pushes qualified accounts into HubSpot
   (`sdr_toolkit/integrations.py`).
5. **Reports throughput** — a funnel + an "output per rep" estimate
   comparing pipeline wall time against a documented manual-effort
   baseline (`sdr_toolkit/reporting.py`).

```
 signal sources          scoring              agents (gated by score)         activation
┌─────────────────┐   ┌───────────────┐   ┌─────────────────────────────┐  ┌───────────────┐
│ hiring surges    │   │  icp_fit()    │   │ ResearchAgent  → dossier    │  │ CSV export     │
│ funding events   │──▶│  signal_score()│─▶│ QualificationAgent → verdict │─▶│ HubSpot        │
│ tech adoption    │   │  combined()   │   │ PersonalizationAgent → seq. │  │ (pluggable)    │
│ website changes  │   └───────────────┘   └─────────────────────────────┘  └───────────────┘
└─────────────────┘      deterministic         LLM-backed, only for              rep queue
   pluggable                 & tunable          nurture-or-better accounts
```

## Quickstart

Zero config, zero API keys, runs offline against a bundled sample
dataset of eight fictional companies:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
sdr-toolkit demo
```

That prints a prioritized queue, a full dossier + drafted sequence for
the top account, and a funnel report.

### Bring your own ICP

```bash
sdr-toolkit prospect --icp examples/icp.yaml --limit 10 --export out/queue.csv
```

`examples/icp.yaml` defines target industries, headcount range,
description/signal keywords, per-signal-type weights, and the
qualification/nurture thresholds — copy it and edit per segment. No code
changes needed.

### Live mode (real Claude calls)

```bash
export ANTHROPIC_API_KEY=sk-...
pip install -e ".[live]"
sdr-toolkit demo --live
```

Offline mode uses `MockLLMClient`, a deterministic stand-in that follows
the exact same labeled-output contract a real prompt asks Claude to
follow — so `--live` is a drop-in swap, not a different code path
(`sdr_toolkit/llm.py`).

### Real (unauthenticated) live signals

Two signal sources can hit the real internet with zero API keys:

- `HiringSurgeSignalSource(..., live=True, greenhouse_tokens={...})` —
  queries Greenhouse's public job board API.
- `WebsiteChangeSignalSource(..., live=True)` — fetches a company's
  actual homepage and keyword-matches it.

Both fall back to the bundled demo data on any network error, so a flaky
connection never crashes a run.

## Testing

```bash
pip install -e ".[dev]"
pytest -q          # 25 tests, fully offline, no API keys required
sdr-toolkit demo    # end-to-end smoke test you can eyeball
```

What's covered:
- **Scoring** (`tests/test_scoring.py`) — ICP fit and signal-weighting
  math, ranking order.
- **Signal sources** (`tests/test_signals.py`) — each adapter correctly
  flags/excludes companies against the bundled dataset, recency decay
  behaves as expected.
- **Agents** (`tests/test_agents.py`) — dossier/sequence/qualification
  output structure, and — importantly — that the qualification
  **verdict** is driven by the deterministic score, not by whatever the
  model happens to say.
- **Orchestrator** (`tests/test_orchestrator.py`) — end-to-end pipeline
  run: sorts correctly, skips agent calls below the nurture bar, only
  drafts sequences for qualified accounts.
- **Reporting** (`tests/test_reporting.py`) — funnel math.
- **CLI** (`tests/test_cli.py`) — `demo` and `prospect` commands,
  including CSV export, run and exit cleanly.

CI (`.github/workflows/ci.yml`) runs the full suite plus a CLI smoke
test on Python 3.10–3.12 on every push.

To sanity-check `--live` beyond CI (uses real API credits): set
`ANTHROPIC_API_KEY` and run `sdr-toolkit demo --live`, then diff the
dossier/sequence output against the offline mock run — it should be
structurally identical (same labeled fields) with real generated
language.

## Design notes

- **Score gates spend.** The pipeline only runs `ResearchAgent` /
  `QualificationAgent` on accounts that clear `nurture_threshold`, and
  only drafts full outreach sequences for accounts that clear
  `qualification_threshold`. This is the actual mechanism behind
  "maximize output per rep": a rep's attention (and the org's LLM spend)
  goes to the accounts most likely to convert, not uniformly across
  every company you can find.
- **Deterministic scoring, LLM-backed reasoning.** `combined_score` and
  the qualification `verdict` bucket are pure functions of the ICP
  config — reproducible and auditable. The model is only ever asked to
  *explain* or *personalize*, never to decide the ranking. See
  `QualificationAgent` in `sdr_toolkit/agents.py`.
- **Everything is an adapter.** `SignalSource`, `LLMClient`, and
  `ActivationAdapter` are small interfaces. Swapping the bundled demo
  data for Clay, Apollo, ZoomInfo, BuiltWith, Crunchbase, or a real
  Outreach/Salesloft sequencer means writing one new class, not touching
  scoring, agents, or reporting.
- **The output-per-rep number is honest about its assumptions.**
  `reporting.py` documents its manual-baseline assumption
  (`MANUAL_MINUTES_PER_QUALIFIED_ACCOUNT`) inline and the CLI refuses to
  print a multiplier in offline mode (mock calls are near-instant, so
  the number would be meaningless) — it only computes one in `--live`
  mode, against real model latency.

## What's stubbed vs. real

| Component | Status |
|---|---|
| Scoring, prioritization, funnel math | Real, fully tested |
| Agents (research/qualification/personalization) | Real prompts + parsing; real Claude calls in `--live` mode |
| Hiring-surge signals | Real live mode via Greenhouse's public API; demo data otherwise |
| Website-change signals | Real live mode (actual HTTP fetch); demo snippet otherwise |
| Funding & tech-adoption signals | Demo data only — swap in Crunchbase/BuiltWith/a blog-RSS watcher |
| CSV export | Fully real |
| HubSpot activation | Real API integration, requires `HUBSPOT_ACCESS_TOKEN` |
| Sample company/contact data | Fictional, bundled for offline dev and CI |

## License

MIT — see [LICENSE](LICENSE).

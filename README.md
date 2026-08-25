# AI SDR/BDR Toolkit

An AI-native SDR & BD toolkit with two distinct modes: a signal-based
prospecting pipeline for quota-driven SDRs, and a long-cycle **business
development** mode — account research, partner intelligence monitoring,
and a partnership-hypothesis chain — for reps whose job isn't a queue to
work this quarter, it's a small number of deep relationships over a much
longer horizon. Built to maximize qualified output per rep, not raw
volume of AI-generated noise, in either mode.

[![CI](https://github.com/joehillthunder/ai-sdr-toolkit/actions/workflows/ci.yml/badge.svg)](https://github.com/joehillthunder/ai-sdr-toolkit/actions/workflows/ci.yml)

*(The package, CLI command, and repo path all stay `ai-sdr-toolkit` /
`sdr-toolkit` / `sdr_toolkit` — only the product name changed.)*

Rolling this out to a team? Read the visual briefing at
**[joehillthunder.github.io/ai-sdr-toolkit](https://joehillthunder.github.io/ai-sdr-toolkit/)**
(or [docs/ONBOARDING.md](docs/ONBOARDING.md) for the same playbook in plain
Markdown) — a phased rollout plan, a 60-minute training session outline,
the daily rep workflow, and what to measure.

## Why this exists

Built as a working reference implementation of what a JD for a sales
development leadership role described as designing an *"AI-native SDR
motion using agents, automation, and signal-based prospecting."* Rather
than write about how I'd approach that, this is the thing itself: a
pipeline that turns raw buying signals into a prioritized, ready-to-work
queue with drafted outreach — runnable, testable, and inspectable end to
end.

## What it does (SDR mode)

This section describes the quota-driven, queue-based pipeline. If your
job is long-cycle partnerships rather than a quarterly number, skip to
[Business development mode](#business-development-mode) below — it's a
genuinely different workflow, not the same pipeline with different labels.

1. **Collects signals** — hiring surges (via Greenhouse or a company's own
   careers page), funding events, tech-stack adoption, and website/product
   language changes — from pluggable sources (`sdr_toolkit/signals/`).
2. **Scores deterministically** — ICP fit + weighted, recency-decayed
   signal strength → a single combined score (`sdr_toolkit/scoring.py`).
   This step is intentionally *not* LLM-based: it's cheap, reproducible,
   and it's what gates which accounts are worth spending a model call on
   at all.
3. **Runs agents only on accounts that clear the bar** — a
   `ResearchAgent` builds an account dossier, a `QualificationAgent`
   explains the verdict, and a `PersonalizationAgent` drafts a 3-touch,
   signal-referencing outreach sequence (`sdr_toolkit/agents.py`), on
   **Claude, OpenAI, or any open-source/local model** (`sdr_toolkit/llm.py`).
4. **Activates the output** — exports a prioritized, rep-ready queue to
   CSV, pushes qualified accounts into HubSpot/Salesforce/Zoho/monday.com, or logs
   everything to a built-in local CRM if you don't have a real one yet
   (`sdr_toolkit/integrations.py`, `sdr_toolkit/simple_crm.py`).
5. **Reports throughput** — a funnel + an "output per rep" estimate
   comparing pipeline wall time against a documented manual-effort
   baseline (`sdr_toolkit/reporting.py`).
6. **Wraps all of that in a point-and-click wizard** (`sdr-toolkit wizard`)
   for a non-technical user: connect an AI + a CRM, describe your business
   in plain language, review a generated lead list with drafted outreach,
   export. See [The Lead Wizard](#the-lead-wizard-non-technical-mode) below.

```
 signal sources          scoring              agents (gated by score)         activation
┌─────────────────┐   ┌───────────────┐   ┌─────────────────────────────┐  ┌───────────────┐
│ hiring surges    │   │  icp_fit()    │   │ ResearchAgent  → dossier    │  │ CSV export     │
│ funding events   │──▶│  signal_score()│─▶│ QualificationAgent → verdict │─▶│ HubSpot/SFDC/  │
│ tech adoption    │   │  combined()   │   │ PersonalizationAgent → seq. │  │ Zoho/built-in  │
│ website changes  │   └───────────────┘   └─────────────────────────────┘  └───────────────┘
└─────────────────┘      deterministic      Claude/OpenAI/open-source,           rep queue
   pluggable                 & tunable       only for qualifying accounts
```

## Business development mode

A quota-carrying SDR works a queue: dozens of accounts a week, score-gated,
templated outreach. BD doesn't work that way — a handful of deep
relationships over quarters, often around a technology that doesn't have
an established buying process yet. `sdr_toolkit/bd/` is built for that job
specifically, not repurposed from the SDR pipeline. Four pieces, all
under `sdr-toolkit bd`:

**1. Long-cycle account research** — the full chain in one call:
org mapping → product strategy → partnership hypothesis → target
executives → recent initiatives → competitive landscape → personalized
outreach → meeting prep (`sdr_toolkit/bd/agents.py:AccountResearchAgent`).

```bash
sdr-toolkit bd account "Toyota" --product "on-device agentic AI" \
  --context "Announced centralized vehicle compute architecture" --live
```

**2. Partner intelligence monitoring** — watch named companies' own
newsroom/engineering-blog RSS feeds and flag announcements that plausibly
open a partnership window against topics you care about:

```bash
sdr-toolkit bd watch --config examples/bd_watchlist.yaml --live
```

```yaml
# examples/bd_watchlist.yaml
companies:
  Dell: "<their newsroom RSS feed URL>"
  Lenovo: "<their newsroom RSS feed URL>"
  Samsung: "<their newsroom RSS feed URL>"
topics:
  - AI PCs
  - local inference
  - spatial computing
  - displays
  - agentic AI
```

No news API, no key — `PartnerAnnouncement`/`parse_feed` read each
company's own public feed (`sdr_toolkit/bd/partner_feeds.py`), and
`PartnerIntelAgent` judges relevance, not just topic overlap.

**3. Technical BD analyst** — point it at an SDK, an API reference, a
GitHub README, or product docs; get back the integration opportunity,
the real engineering scope, and the specific partner pitch
(`TechnicalBDAnalystAgent`):

```bash
sdr-toolkit bd analyze-tech https://github.com/some-partner/their-sdk --product "your platform"
```

**4. The Partnership Hunter** — the flagship chain, company → signal →
opportunity → partner hypothesis → target executive → pitch → next
action, either from a signal you type in or automatically from whatever
`bd watch` just found:

```bash
sdr-toolkit bd hunt --company "Toyota" \
  --signal "Announced centralized vehicle compute architecture" \
  --criteria "On-device multimodal/agentic AI for automotive"

# or run the whole loop: watch, then hunt every signal it finds
sdr-toolkit bd hunt --config examples/bd_watchlist.yaml --criteria "..."
```

```
=== Partnership Opportunity: Toyota ===
Signal:              Announced centralized vehicle compute architecture
Opportunity:         On-device/agentic AI capability that plausibly needs
                      a specialized model or platform partner
Partner hypothesis:  Privately deployable, customizable model running on
                      their own compute -- a technology partnership, not
                      a vendor contract
Target executive:    VP of Platform / Head of AI Strategy
Pitch:                Lead with a concrete technical integration sketch
Next action:          Confirm build-vs-partner is still open, request a
                      20-minute technical scoping call
```

Every field here is a hypothesis to go verify, not a claimed fact —
`target_executive` is a role/title to identify, not a name pulled from a
database; `bd watch` reads what companies chose to publish, not a
comprehensive feed of everything they're doing. That's consistent with
how the rest of this toolkit treats AI output: a strong first draft for
a human who still owns the judgment call, not an oracle.

## The Lead Wizard vs. `sdr-toolkit bd`

The [wizard](#the-lead-wizard-non-technical-mode) below is SDR mode's
non-technical front end — a scored queue with drafted drip sequences. BD
mode is CLI/library-only for now: the output (a rich account dossier, a
partnership chain) isn't naturally a queue to click through, it's
something a rep reads, verifies, and works from directly. `sdr_toolkit.bd`
is a small, clean module if you want to build a UI over it.

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

Three signal sources can hit the real internet with zero API keys:

- `HiringSurgeSignalSource(..., live=True, greenhouse_tokens={...})` —
  queries Greenhouse's public job board API.
- `CareersPageSignalSource(...)` — checks a company's own `/careers` and
  `/jobs` pages. No token needed, so it's the one that actually works for
  an arbitrary company you upload, not just Greenhouse customers.
- `WebsiteChangeSignalSource(..., live=True)` — fetches a company's
  actual homepage and keyword-matches it.

All three fall back gracefully (empty result, or the bundled demo data)
on any network error, so a flaky connection never crashes a run.

## Choose your AI provider

`sdr_toolkit/llm.py` wraps three real providers behind one interface —
swap with `get_client(provider=...)` or, in the CLI, `--live` (Claude) vs.
the wizard's provider picker:

| Provider | `provider=` | Needs | Notes |
|---|---|---|---|
| Claude | `anthropic` | `ANTHROPIC_API_KEY` | `pip install -e ".[live]"` |
| OpenAI | `openai` | `OPENAI_API_KEY` | `pip install -e ".[openai]"` |
| Open-source / local | `open-source` | nothing, usually | Any OpenAI-compatible server — a local **Ollama** or LM Studio instance (`base_url="http://localhost:11434/v1"`), self-hosted vLLM, or a hosted open-weights provider (Together, Groq, Fireworks). `pip install -e ".[openai]"` (used as the generic HTTP client). |
| Offline demo | `mock` | nothing | Deterministic placeholder text, same output contract as the real thing. |

## Choose your CRM

`sdr_toolkit/integrations.py` (+ `sdr_toolkit/simple_crm.py`) implements
`ActivationAdapter` for each of these. All but CSV only touch accounts the
qualification agent marked `qualified`, so a rep's CRM view stays a
filtered queue, not a firehose:

| CRM | Class | Needs |
|---|---|---|
| CSV | `CsvExportAdapter` | nothing — always works |
| Built-in (no CRM yet) | `SimpleCRMAdapter` | nothing — local SQLite file, logs every account |
| HubSpot | `HubSpotAdapter` | `HUBSPOT_ACCESS_TOKEN` |
| Salesforce | `SalesforceAdapter` | `SALESFORCE_INSTANCE_URL`, `SALESFORCE_ACCESS_TOKEN` |
| Zoho | `ZohoAdapter` | `ZOHO_ACCESS_TOKEN`, `ZOHO_API_DOMAIN` |
| monday.com | `MondayAdapter` | `MONDAY_API_TOKEN`, `MONDAY_BOARD_ID` |

`SimpleCRMAdapter` is the "I track leads in a spreadsheet, not a real
CRM" option — a proper local SQLite database (accounts, contacts, and
every drafted sequence touch) with zero setup. Inspect it any time with:

```bash
sdr-toolkit crm list --db sdr_toolkit_crm.db
```

## The Lead Wizard (non-technical mode)

Everything above is also available as a guided, point-and-click flow —
built for a local business owner or a non-technical BD lead, not just an
engineer with a terminal:

```bash
pip install -e ".[web]"
sdr-toolkit wizard
```

Opens a browser to a 3-step wizard:

1. **Connect your tools** — pick an AI provider and paste a key (or skip
   entirely with "just show me a demo"); pick a CRM.
2. **Describe your business** — paste your website URL(s) and describe
   your ideal customer in plain language ("mid-size dental practices in
   Texas hiring front-desk staff"). The wizard proposes targeting
   criteria — editable tags, not YAML — via `sdr_toolkit/icp_builder.py`.
   Three ways to get accounts into the run (mix and match):
   - **Manual** — upload a CSV of accounts you already have in mind.
   - **Research** — click "Suggest candidate companies" and the model
     brainstorms real companies it's aware of that plausibly fit
     (`sdr_toolkit/lead_research.py`). Every result is labeled
     `unverified` — it's a starting list to check, not a database.
   - **Integrations** — paste a [Hunter.io](https://hunter.io) API key
     to auto-fill missing contact emails
     (`sdr_toolkit/enrichment.py:HunterContactFinder`) before scoring runs.

   Provide none of the above and it runs against the bundled sample list
   instead, so you can see the whole flow work first.
3. **Leads & outreach** — a scored, prioritized list of accounts with
   signals, an AI-written dossier, and an editable 3-touch email/LinkedIn
   drip sequence per contact. Where a contact has a LinkedIn/X/Instagram
   handle, one click drafts an additional channel-native touch (a
   connection note, a DM) via `PersonalizationAgent.draft_channel_touch`.
   An SDR reviews and tweaks every draft inline, then exports to
   whichever CRM was chosen in step 1.

**On "an agent that reaches out on LinkedIn/X/Instagram":** deliberately
not built. None of those platforms offer a legitimate API for automating
outbound messages to arbitrary people — doing it via scraping or
unofficial APIs violates their terms and reliably gets accounts banned.
What's here instead is real: channel-native *drafts*, reviewed and sent
by a human in their own LinkedIn/X/Instagram app — the same "AI drafts,
human sends" boundary as email.

The wizard never sends anything on its own — export lands in a CRM or a
CSV. API keys are only used, in-memory, for the actual provider calls the
wizard makes on your behalf — nothing is written to disk unless you
explicitly choose a CRM option that does.

Being honest about scope: this wizard *scores and prioritizes and drafts
for* a set of companies — ones you upload, ones the research step
suggests, or the bundled sample — it doesn't *discover* the universe of
companies matching your ICP from scratch the way Clay/Apollo/ZoomInfo's
proprietary databases do. `SignalSource` / `Company` are exactly the
seams where a real one would plug in.

## Testing

```bash
pip install -e ".[dev,all]"   # dev tools + live/openai/web extras
pytest -q                      # 92 tests, fully offline, no API keys required
sdr-toolkit demo                # end-to-end CLI smoke test you can eyeball
sdr-toolkit wizard               # end-to-end browser smoke test
```

What's covered:
- **Scoring** (`tests/test_scoring.py`) — ICP fit and signal-weighting
  math, ranking order.
- **Signal sources** (`tests/test_signals.py`, `tests/test_careers_signal.py`)
  — each adapter correctly flags/excludes companies against the bundled
  dataset (or a mocked HTTP response), recency decay behaves as expected,
  and network failures degrade gracefully instead of crashing a run.
- **Agents** (`tests/test_agents.py`) — dossier/sequence/qualification
  output structure, and — importantly — that the qualification
  **verdict** is driven by the deterministic score, not by whatever the
  model happens to say.
- **LLM providers** (`tests/test_llm_providers.py`) — the provider
  factory resolves the right client for Claude/OpenAI/open-source/mock,
  and each real client fails fast with a clear error when its
  credentials are missing (no network call attempted).
- **ICP builder** (`tests/test_icp_builder.py`) — generating targeting
  criteria from a plain-language description produces a valid,
  never-empty `ICPConfig`, and a bad URL degrades to `""` instead of
  raising.
- **CRM adapters** (`tests/test_integrations_extra.py`,
  `tests/test_simple_crm.py`) — Salesforce/Zoho fail fast without
  credentials; the built-in SQLite CRM upserts accounts/contacts/sequence
  touches correctly and logs every account, not just qualified ones.
- **Lead research & enrichment** (`tests/test_lead_research.py`,
  `tests/test_enrichment.py`) — AI-suggested companies always come back
  `verified: False`; the Hunter.io client only fills genuinely-missing
  emails and degrades to a no-op (not a crash) without a key or on a
  failed request.
- **Orchestrator** (`tests/test_orchestrator.py`) — end-to-end pipeline
  run: sorts correctly, skips agent calls below the nurture bar, only
  drafts sequences for qualified accounts.
- **Reporting** (`tests/test_reporting.py`) — funnel math.
- **CLI** (`tests/test_cli.py`) — `demo`, `prospect`, and `crm list`
  commands, including CSV export, run and exit cleanly.
- **Wizard backend** (`tests/test_webapp.py`) — every route (`test-llm`,
  `build-icp`, `generate-leads`, `research-leads`, `draft-touch`,
  `export`) via Flask's test client, including custom CSV uploads,
  AI-researched companies flowing into a run, and applying SDR edits
  before export — network calls are mocked, not skipped, so the
  offline-fallback path is actually exercised.
- **BD agents** (`tests/test_bd_agents.py`) — the account research chain,
  technical assessment, and partnership-hunter chain all produce every
  labeled field; `PartnerIntelAgent` correctly wraps an announcement into
  a `PartnershipSignal`.
- **Partner feeds** (`tests/test_bd_partner_feeds.py`) — RSS *and* Atom
  parsing against fixed XML fixtures (namespace-agnostic), malformed XML
  degrades to `[]` instead of raising, and a feed that fails to fetch is
  skipped rather than crashing the whole watch run.
- **BD CLI** (`tests/test_cli.py`) — `bd account`, `bd watch`,
  `bd analyze-tech`, and `bd hunt` (both manual and `--config`-driven)
  run and exit cleanly offline.

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
| Agents (research/qualification/personalization) | Real prompts + parsing; real calls in `--live`/wizard live mode |
| LLM providers (Claude, OpenAI, open-source) | All real API integrations |
| Hiring-surge signals | Real live mode via Greenhouse's public API, or `CareersPageSignalSource` (works for any company); demo data otherwise |
| Website-change signals | Real live mode (actual HTTP fetch); demo snippet otherwise |
| Funding & tech-adoption signals | Demo data only — swap in Crunchbase/BuiltWith/a blog-RSS watcher |
| CSV export | Fully real |
| HubSpot / Salesforce / Zoho activation | Real API integrations, each behind its own credential env vars |
| Built-in CRM (`simple_crm.py`) | Fully real local SQLite — no external account |
| Hunter.io email enrichment | Real API integration, requires `HUNTER_API_KEY` |
| AI-researched candidate companies | Real LLM call, but explicitly unverified output — a brainstorming aid, not a database |
| LinkedIn/X/Instagram touches | Real drafted copy (`PersonalizationAgent.draft_channel_touch`); no automated sending — see the wizard section above for why |
| The wizard's "lead list" | Real scoring/agents against companies *you supply*, the research step suggests, or the bundled sample — not automatic firmographic discovery across the web |
| Sample company/contact data | Fictional, bundled for offline dev and CI |
| BD account research, technical analyst, partnership hunter | Real LLM calls + parsing; `target_executive` is always a role/title hypothesis, never a claimed real person |
| Partner intel (`bd watch`) | Real: fetches each watched company's own public RSS/Atom feed, no API key — but only sees what that company chose to publish there |

## Project layout

```
sdr_toolkit/
  agents.py, orchestrator.py, scoring.py, signals/   # SDR mode
  bd/                                                  # BD mode
    agents.py        AccountResearchAgent, PartnerIntelAgent,
                      TechnicalBDAnalystAgent, PartnershipHunterAgent
    partner_feeds.py RSS/Atom fetch + parse + watch_partners()
    models.py         BDAccountDossier, PartnershipOpportunity, ...
  llm.py, integrations.py, simple_crm.py             # shared providers/CRMs
  webapp/                                              # the SDR-mode wizard
  cli.py                                                # `sdr-toolkit ...` / `sdr-toolkit bd ...`
```

## License

MIT — see [LICENSE](LICENSE).

"""Data model for business-development / partnership workflows.

Kept separate from `sdr_toolkit.models` on purpose: BD is a different job
than SDR prospecting. There's no queue to work through a quota this
quarter -- there's a small number of long, deep relationships, so the
unit of work here is a rich account dossier or a partnership hypothesis,
not a scored row in a priority list.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class BDAccountDossier:
    """The long-cycle BD research chain: org mapping through meeting prep."""

    company: str
    org_mapping: str
    product_strategy: str
    partnership_hypothesis: str
    target_executives: list[str]
    recent_initiatives: str
    competitive_landscape: str
    personalized_outreach: str
    meeting_prep: list[str]
    generated_by: str


@dataclass
class PartnerAnnouncement:
    """One item pulled from a watched company's own newsroom/blog feed."""

    company: str
    title: str
    url: str
    published_at: date | None
    summary: str


@dataclass
class PartnershipSignal:
    """An announcement the partner-intel agent judged relevant to a
    watchlist of partnership topics."""

    announcement: PartnerAnnouncement
    topics_matched: list[str]
    relevance: str
    generated_by: str


@dataclass
class TechnicalAssessment:
    """A technical BD analyst's read on an SDK/API/repo/product doc."""

    source: str
    integration_opportunity: str
    engineering_effort: str
    partner_pitch: str
    generated_by: str


@dataclass
class PartnershipOpportunity:
    """The flagship chain: company -> signal -> opportunity -> partner
    hypothesis -> target executive -> pitch -> next action."""

    company: str
    signal: str
    opportunity: str
    partner_hypothesis: str
    target_executive: str
    pitch: str
    next_action: str
    generated_by: str

"""Core data model shared across the pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass
class Company:
    id: str
    name: str
    domain: str
    industry: str
    employee_count: int
    headquarters: str
    description: str


@dataclass
class Contact:
    id: str
    company_id: str
    name: str
    title: str
    seniority: str  # "ic" | "manager" | "director" | "vp" | "c_level"
    email: Optional[str] = None
    linkedin_url: Optional[str] = None


@dataclass
class Signal:
    id: str
    company_id: str
    type: str  # "hiring_surge" | "funding" | "tech_adoption" | "website_change"
    strength: float  # 0.0-1.0, how strong/relevant this individual signal is
    detected_at: date
    evidence: str
    source: str


@dataclass
class ScoredAccount:
    company: Company
    icp_fit: float
    signal_score: float
    combined_score: float
    signals: list[Signal] = field(default_factory=list)


@dataclass
class Dossier:
    company_id: str
    summary: str
    pain_points: list[str]
    recommended_angle: str
    generated_by: str


@dataclass
class OutreachTouch:
    channel: str  # "email" | "linkedin"
    day_offset: int
    subject: Optional[str]
    body: str


@dataclass
class OutreachSequence:
    contact_id: str
    touches: list[OutreachTouch]


@dataclass
class QualificationResult:
    company_id: str
    verdict: str  # "qualified" | "nurture" | "disqualified"
    rationale: str
    combined_score: float


@dataclass
class ProspectPackage:
    scored_account: ScoredAccount
    contacts: list[Contact]
    dossier: Optional[Dossier]
    qualification: Optional[QualificationResult]
    sequences: dict[str, OutreachSequence] = field(default_factory=dict)

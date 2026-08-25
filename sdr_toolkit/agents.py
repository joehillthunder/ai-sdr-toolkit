"""LLM-backed agents.

Each agent has one job and a strict, labeled output contract (e.g.
`SUMMARY:` / `PAIN_POINTS:` / `ANGLE:`) so the same parser works whether
the underlying client is the offline `MockLLMClient` or a live Claude
model — the prompt just asks the model to follow the same contract the
mock already satisfies.

Agents never invent the qualification score themselves; `QualificationAgent`
takes the deterministic `combined_score` from scoring.py as ground truth
and only asks the model to reason about *why*, so a model having a bad day
can't silently derail the queue a rep works from.
"""

from __future__ import annotations

from .llm import LLMClient
from .models import Company, Contact, Dossier, OutreachSequence, OutreachTouch, QualificationResult, ScoredAccount, Signal
from .text import parse_labeled as _parse_labeled


def _signal_context(signals: list[Signal]) -> str:
    if not signals:
        return "No specific signals detected; general ICP fit only."
    lines = [f"- [{s.type}] {s.evidence} (strength={s.strength}, source={s.source})" for s in signals]
    return "\n".join(lines)


class ResearchAgent:
    """Synthesizes raw signals + firmographics into an account dossier."""

    SYSTEM = (
        "You are a B2B sales research analyst building an account dossier. "
        "Respond ONLY in this exact labeled format:\n"
        "SUMMARY: <one or two sentence account summary>\n"
        "PAIN_POINTS: <semicolon-separated likely pain points>\n"
        "ANGLE: <one sentence recommended outreach angle referencing the strongest signal>"
    )

    def __init__(self, llm: LLMClient):
        self.llm = llm

    def build_dossier(self, company: Company, signals: list[Signal]) -> Dossier:
        prompt = (
            f"Company: {company.name}\n"
            f"Industry: {company.industry}\n"
            f"Employees: {company.employee_count}\n"
            f"Description: {company.description}\n\n"
            f"Signals detected:\n{_signal_context(signals)}\n\n"
            "Build the dossier now."
        )
        raw = self.llm.generate(self.SYSTEM, prompt)
        parsed = _parse_labeled(raw, ["SUMMARY", "PAIN_POINTS", "ANGLE"])
        pain_points = [p.strip() for p in parsed["PAIN_POINTS"].split(";") if p.strip()]
        return Dossier(
            company_id=company.id,
            summary=parsed["SUMMARY"] or "No summary generated.",
            pain_points=pain_points,
            recommended_angle=parsed["ANGLE"] or "Lead with ICP fit.",
            generated_by=getattr(self.llm, "name", self.llm.__class__.__name__),
        )


class PersonalizationAgent:
    """Drafts a signal-referencing, multi-channel outreach sequence."""

    SYSTEM = (
        "You are an SDR writing a concise, non-generic 3-touch outreach sequence "
        "(email, LinkedIn, email) that references a specific buying signal. "
        "Respond ONLY in this exact labeled format:\n"
        "TOUCH_1_EMAIL_SUBJECT: <subject>\n"
        "TOUCH_1_EMAIL_BODY: <body, under 80 words>\n"
        "TOUCH_2_LINKEDIN_BODY: <body, under 40 words>\n"
        "TOUCH_3_EMAIL_SUBJECT: <subject>\n"
        "TOUCH_3_EMAIL_BODY: <breakup email body, under 50 words>"
    )

    def __init__(self, llm: LLMClient):
        self.llm = llm

    def draft_sequence(
        self, company: Company, contact: Contact, dossier: Dossier, signals: list[Signal]
    ) -> OutreachSequence:
        prompt = (
            f"Company: {company.name}\n"
            f"Contact: {contact.name}, {contact.title}\n"
            f"Dossier summary: {dossier.summary}\n"
            f"Recommended angle: {dossier.recommended_angle}\n"
            f"Signals:\n{_signal_context(signals)}\n\n"
            "Draft the sequence now."
        )
        raw = self.llm.generate(self.SYSTEM, prompt)
        parsed = _parse_labeled(
            raw,
            [
                "TOUCH_1_EMAIL_SUBJECT",
                "TOUCH_1_EMAIL_BODY",
                "TOUCH_2_LINKEDIN_BODY",
                "TOUCH_3_EMAIL_SUBJECT",
                "TOUCH_3_EMAIL_BODY",
            ],
        )
        touches = [
            OutreachTouch("email", 0, parsed["TOUCH_1_EMAIL_SUBJECT"], parsed["TOUCH_1_EMAIL_BODY"]),
            OutreachTouch("linkedin", 3, None, parsed["TOUCH_2_LINKEDIN_BODY"]),
            OutreachTouch("email", 7, parsed["TOUCH_3_EMAIL_SUBJECT"], parsed["TOUCH_3_EMAIL_BODY"]),
        ]
        return OutreachSequence(contact_id=contact.id, touches=touches)

    CHANNEL_SYSTEM = (
        "You are an SDR writing ONE additional outreach touch for a specific "
        "channel, referencing a buying signal. Keep it native to the channel: a "
        "LinkedIn connection note is under 300 characters with no links; an X/Twitter "
        "DM is short and casual; an Instagram DM is short, personal, and low-pressure. "
        "Never write anything that reads as automated or mass-sent. Respond ONLY in "
        "this exact labeled format:\n"
        "BODY: <the message text>"
    )

    #: channel key -> (max characters, human description used in the prompt)
    CHANNELS = {
        "linkedin_connection_note": (300, "a LinkedIn connection request note"),
        "x_dm": (280, "an X (Twitter) direct message"),
        "instagram_dm": (400, "an Instagram direct message"),
    }

    def draft_channel_touch(
        self,
        company: Company,
        contact: Contact,
        dossier: Dossier,
        signals: list[Signal],
        channel: str,
        day_offset: int = 0,
    ) -> OutreachTouch:
        if channel not in self.CHANNELS:
            raise ValueError(f"Unknown channel: {channel!r}. Expected one of {list(self.CHANNELS)}.")
        max_chars, description = self.CHANNELS[channel]
        prompt = (
            f"Channel: {description} (hard limit {max_chars} characters)\n"
            f"Company: {company.name}\n"
            f"Contact: {contact.name}, {contact.title}\n"
            f"Recommended angle: {dossier.recommended_angle}\n"
            f"Signals:\n{_signal_context(signals)}\n\n"
            "Draft it now."
        )
        raw = self.llm.generate(self.CHANNEL_SYSTEM, prompt)
        parsed = _parse_labeled(raw, ["BODY"])
        body = (parsed["BODY"] or "")[:max_chars]
        return OutreachTouch(channel=channel, day_offset=day_offset, subject=None, body=body)


class QualificationAgent:
    """Produces a human-readable qualification verdict.

    The verdict bucket is derived from the deterministic `combined_score`
    against the ICP's thresholds (never from the model). The model only
    supplies the rationale a rep can use in a call or an SDR manager can
    audit — this keeps the queue ordering trustworthy and reproducible.
    """

    SYSTEM = (
        "You are a sales qualification analyst. Explain, in 1-2 sentences, why an "
        "account was qualified/nurture/disqualified given its fit and signal scores. "
        "Respond ONLY in this exact labeled format:\n"
        "VERDICT: <qualified|nurture|disqualified>\n"
        "RATIONALE: <1-2 sentence justification>"
    )

    def __init__(self, llm: LLMClient):
        self.llm = llm

    def qualify(self, scored: ScoredAccount, dossier: Dossier | None, icp) -> QualificationResult:
        if scored.combined_score >= icp.qualification_threshold:
            verdict = "qualified"
        elif scored.combined_score >= icp.nurture_threshold:
            verdict = "nurture"
        else:
            verdict = "disqualified"

        prompt = (
            f"Company: {scored.company.name}\n"
            f"ICP fit: {scored.icp_fit}\n"
            f"Signal score: {scored.signal_score}\n"
            f"Combined score: {scored.combined_score}\n"
            f"Determined verdict (do not change): {verdict}\n"
            f"Dossier: {dossier.summary if dossier else 'n/a'}\n\n"
            "Explain the verdict now."
        )
        raw = self.llm.generate(self.SYSTEM, prompt)
        parsed = _parse_labeled(raw, ["VERDICT", "RATIONALE"])
        rationale = parsed["RATIONALE"] or "Score-based determination; no rationale generated."
        return QualificationResult(
            company_id=scored.company.id,
            verdict=verdict,
            rationale=rationale,
            combined_score=scored.combined_score,
        )

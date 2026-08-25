"""BD agents: account research, technical assessment, and the
partnership-hypothesis chain.

Same design rule as sdr_toolkit/agents.py: every agent has a strict,
labeled output contract so MockLLMClient and a real model produce
structurally identical output, and every agent produces *reasoning and
drafts*, never a claim of verified fact (a target executive here is a
role/title hypothesis to go confirm, not a scraped org chart).
"""

from __future__ import annotations

from ..llm import LLMClient
from ..text import parse_labeled
from .models import (
    BDAccountDossier,
    PartnerAnnouncement,
    PartnershipOpportunity,
    PartnershipSignal,
    TechnicalAssessment,
)


class AccountResearchAgent:
    """Long-cycle BD account research: org mapping through meeting prep,
    in one structured pass rather than eight separate calls -- BD moves
    slowly by nature, but a rep's time on any given call still shouldn't."""

    SYSTEM = (
        "You are a business development researcher producing an account research chain "
        "for a long-cycle technology partnership (not a quota-driven sales deal). Be "
        "specific to the company and the stated product/technology; never write generic "
        "boilerplate. Respond ONLY in this exact labeled format:\n"
        "ORG_MAPPING: <how their relevant org is structured -- who would own this decision>\n"
        "PRODUCT_STRATEGY: <what they're building and where the roadmap is headed>\n"
        "PARTNERSHIP_HYPOTHESIS: <why a partnership, specifically, beats a vendor sale here>\n"
        "TARGET_EXECUTIVES: <semicolon-separated titles/roles most likely to own this>\n"
        "RECENT_INITIATIVES: <what's publicly indicating momentum in this area>\n"
        "COMPETITIVE_LANDSCAPE: <who else is in this space with them, and the gap you'd fill>\n"
        "PERSONALIZED_OUTREACH: <one paragraph opening angle referencing something specific>\n"
        "MEETING_PREP: <semicolon-separated prep bullets: what to confirm, what to bring, what to ask>"
    )

    def __init__(self, llm: LLMClient):
        self.llm = llm

    def research(self, company: str, our_product: str = "", context: str = "") -> BDAccountDossier:
        prompt = (
            f"Target company: {company}\n"
            f"Our product/technology: {our_product or '(not specified)'}\n"
            f"Additional context: {context or '(none provided)'}\n\n"
            "Produce the account research chain now."
        )
        raw = self.llm.generate(self.SYSTEM, prompt)
        parsed = parse_labeled(
            raw,
            [
                "ORG_MAPPING",
                "PRODUCT_STRATEGY",
                "PARTNERSHIP_HYPOTHESIS",
                "TARGET_EXECUTIVES",
                "RECENT_INITIATIVES",
                "COMPETITIVE_LANDSCAPE",
                "PERSONALIZED_OUTREACH",
                "MEETING_PREP",
            ],
        )
        return BDAccountDossier(
            company=company,
            org_mapping=parsed["ORG_MAPPING"],
            product_strategy=parsed["PRODUCT_STRATEGY"],
            partnership_hypothesis=parsed["PARTNERSHIP_HYPOTHESIS"],
            target_executives=[t.strip() for t in parsed["TARGET_EXECUTIVES"].split(";") if t.strip()],
            recent_initiatives=parsed["RECENT_INITIATIVES"],
            competitive_landscape=parsed["COMPETITIVE_LANDSCAPE"],
            personalized_outreach=parsed["PERSONALIZED_OUTREACH"],
            meeting_prep=[m.strip() for m in parsed["MEETING_PREP"].split(";") if m.strip()],
            generated_by=getattr(self.llm, "name", self.llm.__class__.__name__),
        )


class PartnerIntelAgent:
    """Judges whether one announcement from a watched company creates a
    partnership opening against a list of topics you care about."""

    SYSTEM = (
        "You are a partnership relevance analyst. Given one company announcement and a list "
        "of topics a BD team is watching for, decide whether this announcement plausibly "
        "creates a partnership opening -- not just whether it's topically related, but "
        "whether it suggests a build-vs-partner decision is actively in play. Respond ONLY "
        "in this exact labeled format:\n"
        "RELEVANT: <yes|no>\n"
        "TOPICS: <comma-separated subset of the watched topics this actually matches>\n"
        "RELEVANCE: <one or two sentences on why this is or isn't a partnership opening>"
    )

    def __init__(self, llm: LLMClient):
        self.llm = llm

    def evaluate(self, announcement: PartnerAnnouncement, topics: list[str]) -> PartnershipSignal | None:
        prompt = (
            f"Company: {announcement.company}\n"
            f"Announcement: {announcement.title}\n"
            f"Summary: {announcement.summary}\n"
            f"URL: {announcement.url}\n"
            f"Watched topics: {', '.join(topics)}\n\n"
            "Evaluate it now."
        )
        raw = self.llm.generate(self.SYSTEM, prompt)
        parsed = parse_labeled(raw, ["RELEVANT", "TOPICS", "RELEVANCE"])
        if not parsed["RELEVANT"].strip().lower().startswith("y"):
            return None
        topics_matched = [t.strip() for t in parsed["TOPICS"].split(",") if t.strip()]
        return PartnershipSignal(
            announcement=announcement,
            topics_matched=topics_matched,
            relevance=parsed["RELEVANCE"] or "",
            generated_by=getattr(self.llm, "name", self.llm.__class__.__name__),
        )


class TechnicalBDAnalystAgent:
    """Reads an SDK/API/repo/product-doc text and translates it into BD
    terms: what the integration opportunity is, what it would take to
    build, and what you'd pitch the partner."""

    SYSTEM = (
        "You are a technical partnership analyst. Given the text of an SDK, API reference, "
        "GitHub repo README, or product documentation, explain the integration opportunity in "
        "business-development terms. Respond ONLY in this exact labeled format:\n"
        "INTEGRATION_OPPORTUNITY: <what specifically could be integrated, and where it plugs in>\n"
        "ENGINEERING_EFFORT: <realistic scope -- what a team would actually need to build>\n"
        "PARTNER_PITCH: <the specific thing you'd say to the partner to make this compelling to them>"
    )

    def __init__(self, llm: LLMClient):
        self.llm = llm

    def analyze(self, source: str, doc_text: str, our_product: str = "") -> TechnicalAssessment:
        prompt = (
            f"Source: {source}\n"
            f"Our product/technology (for pitch framing): {our_product or '(not specified)'}\n\n"
            f"Documentation text:\n{doc_text[:6000]}\n\n"
            "Produce the technical BD assessment now."
        )
        raw = self.llm.generate(self.SYSTEM, prompt)
        parsed = parse_labeled(raw, ["INTEGRATION_OPPORTUNITY", "ENGINEERING_EFFORT", "PARTNER_PITCH"])
        return TechnicalAssessment(
            source=source,
            integration_opportunity=parsed["INTEGRATION_OPPORTUNITY"],
            engineering_effort=parsed["ENGINEERING_EFFORT"],
            partner_pitch=parsed["PARTNER_PITCH"],
            generated_by=getattr(self.llm, "name", self.llm.__class__.__name__),
        )


class PartnershipHunterAgent:
    """The flagship chain: company -> signal -> opportunity -> partner
    hypothesis -> target executive -> pitch -> next action."""

    SYSTEM = (
        "You are a BD partnership strategist turning one market signal into a partnership "
        "opportunity chain. Think concretely, the way a technical BD lead would -- name a "
        "plausible category of technology, not a vague synergy. Respond ONLY in this exact "
        "labeled format:\n"
        "OPPORTUNITY: <what technology/capability opportunity this signal implies>\n"
        "PARTNER_HYPOTHESIS: <the specific partnership angle -- what you'd bring them>\n"
        "TARGET_EXECUTIVE: <role/title most likely to own this decision -- not a named person>\n"
        "PITCH: <the opening technical/business hook for outreach>\n"
        "NEXT_ACTION: <the single next concrete step>"
    )

    def __init__(self, llm: LLMClient):
        self.llm = llm

    def hunt(self, company: str, signal: str, partnership_criteria: str = "") -> PartnershipOpportunity:
        prompt = (
            f"Company: {company}\n"
            f"Signal: {signal}\n"
            f"Our partnership criteria/ICP: {partnership_criteria or '(not specified)'}\n\n"
            "Build the partnership opportunity chain now."
        )
        raw = self.llm.generate(self.SYSTEM, prompt)
        parsed = parse_labeled(
            raw, ["OPPORTUNITY", "PARTNER_HYPOTHESIS", "TARGET_EXECUTIVE", "PITCH", "NEXT_ACTION"]
        )
        return PartnershipOpportunity(
            company=company,
            signal=signal,
            opportunity=parsed["OPPORTUNITY"],
            partner_hypothesis=parsed["PARTNER_HYPOTHESIS"],
            target_executive=parsed["TARGET_EXECUTIVE"],
            pitch=parsed["PITCH"],
            next_action=parsed["NEXT_ACTION"],
            generated_by=getattr(self.llm, "name", self.llm.__class__.__name__),
        )

    def hunt_from_signal(self, ps: PartnershipSignal, partnership_criteria: str = "") -> PartnershipOpportunity:
        """Feed a PartnerIntelAgent finding straight into the chain --
        this is the "continuously turn signals into opportunities" loop."""
        signal_text = f"{ps.announcement.title} — {ps.relevance}"
        return self.hunt(ps.announcement.company, signal_text, partnership_criteria)

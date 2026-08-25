"""Ties signal collection, scoring, and agents into one pipeline run.

This is the "AI-native SDR motion": cheap, deterministic scoring gates
which accounts are worth spending LLM calls on at all, so a rep's (and a
budget's) expensive agentic work — dossiers, personalized sequences —
only ever runs on the accounts most likely to convert. That's the whole
point of signal-based prioritization: maximize qualified output per rep,
not raw volume of AI-generated noise.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from .agents import PersonalizationAgent, QualificationAgent, ResearchAgent
from .config import ICPConfig
from .llm import LLMClient
from .models import Company, Contact, ProspectPackage, Signal
from .scoring import prioritize
from .signals.base import SignalSource


@dataclass
class PipelineResult:
    packages: list[ProspectPackage]
    elapsed_seconds: float
    signals_collected: int


class Pipeline:
    def __init__(
        self,
        icp: ICPConfig,
        llm_client: LLMClient,
        signal_sources: list[SignalSource],
    ):
        self.icp = icp
        self.llm = llm_client
        self.signal_sources = signal_sources
        self.research_agent = ResearchAgent(llm_client)
        self.personalization_agent = PersonalizationAgent(llm_client)
        self.qualification_agent = QualificationAgent(llm_client)

    def collect_signals(self, companies: list[Company]) -> dict[str, list[Signal]]:
        by_company: dict[str, list[Signal]] = {c.id: [] for c in companies}
        for source in self.signal_sources:
            for signal in source.collect(companies):
                by_company.setdefault(signal.company_id, []).append(signal)
        return by_company

    def run(
        self,
        companies: list[Company],
        contacts_by_company: dict[str, list[Contact]],
        draft_sequences_for: tuple[str, ...] = ("qualified",),
        limit: int | None = None,
    ) -> PipelineResult:
        start = time.perf_counter()

        signals_by_company = self.collect_signals(companies)
        total_signals = sum(len(v) for v in signals_by_company.values())

        scored_accounts = prioritize(companies, signals_by_company, self.icp)
        if limit:
            scored_accounts = scored_accounts[:limit]

        packages: list[ProspectPackage] = []
        for scored in scored_accounts:
            contacts = contacts_by_company.get(scored.company.id, [])

            # Only spend LLM calls building a dossier on accounts that at
            # least clear the nurture bar -- everything below that is
            # rejected on deterministic score alone.
            if scored.combined_score < self.icp.nurture_threshold:
                packages.append(
                    ProspectPackage(
                        scored_account=scored,
                        contacts=contacts,
                        dossier=None,
                        qualification=None,
                        sequences={},
                    )
                )
                continue

            dossier = self.research_agent.build_dossier(scored.company, scored.signals)
            qualification = self.qualification_agent.qualify(scored, dossier, self.icp)

            sequences = {}
            if qualification.verdict in draft_sequences_for:
                for contact in contacts:
                    sequences[contact.id] = self.personalization_agent.draft_sequence(
                        scored.company, contact, dossier, scored.signals
                    )

            packages.append(
                ProspectPackage(
                    scored_account=scored,
                    contacts=contacts,
                    dossier=dossier,
                    qualification=qualification,
                    sequences=sequences,
                )
            )

        elapsed = time.perf_counter() - start
        return PipelineResult(packages=packages, elapsed_seconds=elapsed, signals_collected=total_signals)

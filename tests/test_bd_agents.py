from sdr_toolkit.bd.agents import (
    AccountResearchAgent,
    PartnerIntelAgent,
    PartnershipHunterAgent,
    TechnicalBDAnalystAgent,
)
from sdr_toolkit.bd.models import PartnerAnnouncement
from sdr_toolkit.llm import MockLLMClient

LLM = MockLLMClient()


def test_account_research_agent_produces_full_chain():
    dossier = AccountResearchAgent(LLM).research(
        "Toyota", our_product="on-device agentic AI", context="Centralized vehicle compute architecture"
    )
    assert dossier.company == "Toyota"
    assert dossier.org_mapping
    assert dossier.product_strategy
    assert dossier.partnership_hypothesis
    assert isinstance(dossier.target_executives, list) and dossier.target_executives
    assert dossier.recent_initiatives
    assert dossier.competitive_landscape
    assert dossier.personalized_outreach
    assert isinstance(dossier.meeting_prep, list) and dossier.meeting_prep
    assert dossier.generated_by == "mock"


def test_partner_intel_agent_returns_signal_when_relevant():
    announcement = PartnerAnnouncement(
        company="Dell", title="Dell unveils new AI PC lineup", url="https://dell.example/x",
        published_at=None, summary="On-device inference for the next generation of laptops.",
    )
    signal = PartnerIntelAgent(LLM).evaluate(announcement, ["ai pcs", "local inference"])
    assert signal is not None
    assert signal.announcement is announcement
    assert signal.topics_matched
    assert signal.relevance
    assert signal.generated_by == "mock"


def test_technical_bd_analyst_produces_assessment():
    assessment = TechnicalBDAnalystAgent(LLM).analyze(
        "https://example.com/sdk-docs",
        "This SDK exposes a REST API with a plugin architecture for custom inference pipelines.",
        our_product="on-device inference engine",
    )
    assert assessment.source == "https://example.com/sdk-docs"
    assert assessment.integration_opportunity
    assert assessment.engineering_effort
    assert assessment.partner_pitch


def test_partnership_hunter_produces_full_chain():
    hunter = PartnershipHunterAgent(LLM)
    opportunity = hunter.hunt(
        "Toyota", "Announced centralized vehicle compute architecture",
        partnership_criteria="On-device multimodal/agentic AI for automotive",
    )
    assert opportunity.company == "Toyota"
    assert opportunity.signal
    assert opportunity.opportunity
    assert opportunity.partner_hypothesis
    assert opportunity.target_executive
    assert opportunity.pitch
    assert opportunity.next_action


def test_partnership_hunter_hunt_from_signal():
    announcement = PartnerAnnouncement(
        company="Samsung", title="Samsung announces spatial computing display", url="https://samsung.example/y",
        published_at=None, summary="New spatial display tech for agentic AI interfaces.",
    )
    signal = PartnerIntelAgent(LLM).evaluate(announcement, ["spatial computing", "displays"])
    assert signal is not None

    opportunity = PartnershipHunterAgent(LLM).hunt_from_signal(signal, partnership_criteria="Display partnerships")
    assert opportunity.company == "Samsung"
    assert "Samsung announces spatial computing display" in opportunity.signal

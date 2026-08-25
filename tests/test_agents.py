from datetime import date

from sdr_toolkit.agents import PersonalizationAgent, QualificationAgent, ResearchAgent
from sdr_toolkit.config import ICPConfig
from sdr_toolkit.llm import MockLLMClient
from sdr_toolkit.models import ScoredAccount, Signal
from sdr_toolkit.signals.demo_data import demo_companies, demo_contacts

LLM = MockLLMClient()
ICP = ICPConfig.default()
COMPANY = next(c for c in demo_companies() if c.id == "nimbus-voice")
CONTACT = next(c for c in demo_contacts() if c.company_id == "nimbus-voice")
SIGNALS = [Signal("1", COMPANY.id, "hiring_surge", 0.9, date(2026, 8, 20), "4 open AI roles", "test")]


def test_research_agent_produces_structured_dossier():
    dossier = ResearchAgent(LLM).build_dossier(COMPANY, SIGNALS)
    assert dossier.company_id == COMPANY.id
    assert dossier.summary
    assert isinstance(dossier.pain_points, list) and dossier.pain_points
    assert dossier.recommended_angle
    assert dossier.generated_by == "mock"


def test_personalization_agent_produces_three_touch_sequence():
    dossier = ResearchAgent(LLM).build_dossier(COMPANY, SIGNALS)
    sequence = PersonalizationAgent(LLM).draft_sequence(COMPANY, CONTACT, dossier, SIGNALS)
    assert sequence.contact_id == CONTACT.id
    assert len(sequence.touches) == 3
    assert [t.channel for t in sequence.touches] == ["email", "linkedin", "email"]
    assert all(t.body for t in sequence.touches)
    assert sequence.touches[0].subject and sequence.touches[2].subject
    assert sequence.touches[1].subject is None


def test_qualification_agent_verdict_follows_deterministic_thresholds_not_llm():
    high = ScoredAccount(COMPANY, icp_fit=0.9, signal_score=0.9, combined_score=0.9, signals=SIGNALS)
    mid = ScoredAccount(COMPANY, icp_fit=0.4, signal_score=0.4, combined_score=0.4, signals=SIGNALS)
    low = ScoredAccount(COMPANY, icp_fit=0.1, signal_score=0.1, combined_score=0.1, signals=[])

    agent = QualificationAgent(LLM)
    assert agent.qualify(high, None, ICP).verdict == "qualified"
    assert agent.qualify(mid, None, ICP).verdict == "nurture"
    assert agent.qualify(low, None, ICP).verdict == "disqualified"


def test_qualification_agent_includes_rationale_text():
    scored = ScoredAccount(COMPANY, icp_fit=0.9, signal_score=0.9, combined_score=0.9, signals=SIGNALS)
    result = QualificationAgent(LLM).qualify(scored, None, ICP)
    assert result.rationale
    assert result.combined_score == 0.9


def test_draft_channel_touch_respects_channel_char_limits():
    dossier = ResearchAgent(LLM).build_dossier(COMPANY, SIGNALS)
    for channel, (max_chars, _) in PersonalizationAgent.CHANNELS.items():
        touch = PersonalizationAgent(LLM).draft_channel_touch(COMPANY, CONTACT, dossier, SIGNALS, channel)
        assert touch.channel == channel
        assert touch.subject is None
        assert touch.body
        assert len(touch.body) <= max_chars


def test_draft_channel_touch_rejects_unknown_channel():
    dossier = ResearchAgent(LLM).build_dossier(COMPANY, SIGNALS)
    try:
        PersonalizationAgent(LLM).draft_channel_touch(COMPANY, CONTACT, dossier, SIGNALS, "carrier_pigeon")
        assert False, "expected ValueError"
    except ValueError:
        pass

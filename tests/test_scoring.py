from datetime import date

from sdr_toolkit.config import ICPConfig
from sdr_toolkit.models import Signal
from sdr_toolkit.scoring import combined_score, icp_fit, prioritize, signal_score
from sdr_toolkit.signals.demo_data import demo_companies


def _company(company_id: str):
    return next(c for c in demo_companies() if c.id == company_id)


def test_icp_fit_rewards_industry_and_keyword_match():
    icp = ICPConfig.default()
    nimbus_fit = icp_fit(_company("nimbus-voice"), icp)
    ledger_fit = icp_fit(_company("ledger-peak"), icp)
    assert 0.0 <= ledger_fit <= 1.0
    assert 0.0 <= nimbus_fit <= 1.0
    assert nimbus_fit > ledger_fit


def test_icp_fit_out_of_range_headcount_is_penalized():
    icp = ICPConfig.default()
    tiny = _company("chatterbox")
    huge_icp = ICPConfig(**{**icp.__dict__, "min_employees": 5000, "max_employees": 10000})
    assert icp_fit(tiny, huge_icp) < icp_fit(tiny, icp)


def test_signal_score_weights_by_type_and_strength():
    icp = ICPConfig.default()
    strong_hire = Signal("1", "x", "hiring_surge", 0.9, date(2026, 8, 20), "evidence", "test")
    weak_website = Signal("2", "x", "website_change", 0.2, date(2026, 8, 20), "evidence", "test")

    score_a = signal_score([strong_hire], icp)
    score_b = signal_score([weak_website], icp)
    assert score_a > score_b
    assert signal_score([], icp) == 0.0


def test_signal_score_rewards_corroborating_signals():
    icp = ICPConfig.default()
    one = [Signal("1", "x", "hiring_surge", 0.5, date(2026, 8, 20), "e", "t")]
    two = one + [Signal("2", "x", "funding", 0.5, date(2026, 8, 20), "e", "t")]
    assert signal_score(two, icp) >= signal_score(one, icp)


def test_combined_score_is_weighted_average():
    icp = ICPConfig.default()
    assert combined_score(1.0, 0.0, icp) == icp.icp_weight
    assert combined_score(0.0, 1.0, icp) == icp.signal_weight


def test_prioritize_sorts_descending_by_combined_score():
    icp = ICPConfig.default()
    companies = demo_companies()
    signals = {
        "nimbus-voice": [Signal("1", "nimbus-voice", "hiring_surge", 0.9, date(2026, 8, 20), "e", "t")],
        "greencart": [],
    }
    scored = prioritize(companies, signals, icp)
    scores = [s.combined_score for s in scored]
    assert scores == sorted(scores, reverse=True)
    # the company with a real signal + better fit should outrank one with none
    ranked_ids = [s.company.id for s in scored]
    assert ranked_ids.index("nimbus-voice") < ranked_ids.index("greencart")

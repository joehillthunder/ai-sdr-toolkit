"""Deterministic scoring: ICP fit, signal strength, and prioritization.

Scoring is kept rule-based and fully deterministic on purpose — it's the
part of the pipeline a sales leader needs to trust and tune without
worrying about LLM non-determinism. The agents (see agents.py) add
judgment and language on top of these numbers; they never override them.
"""

from __future__ import annotations

from .config import ICPConfig
from .models import Company, ScoredAccount, Signal


def icp_fit(company: Company, icp: ICPConfig) -> float:
    """0-1 score for how well a company matches the target profile."""
    score = 0.0
    weight_total = 0.0

    # industry match
    weight_total += 1.0
    if company.industry.lower() in [i.lower() for i in icp.target_industries]:
        score += 1.0

    # employee count in range
    weight_total += 1.0
    if icp.min_employees <= company.employee_count <= icp.max_employees:
        score += 1.0

    # description keyword density
    weight_total += 1.0
    if icp.description_keywords:
        text = company.description.lower()
        hits = sum(1 for kw in icp.description_keywords if kw.lower() in text)
        score += min(1.0, hits / max(1, len(icp.description_keywords) // 2 or 1))

    return round(score / weight_total, 3) if weight_total else 0.0


def signal_score(signals: list[Signal], icp: ICPConfig) -> float:
    """0-1 aggregate score across all signals for one company, weighted by
    signal type and each signal's own strength/recency."""
    if not signals:
        return 0.0
    weighted_total = 0.0
    weight_sum = 0.0
    for sig in signals:
        w = icp.signal_type_weights.get(sig.type, 0.5)
        weighted_total += w * sig.strength
        weight_sum += w
    if weight_sum == 0:
        return 0.0
    # more corroborating signals should push the score up, not just average
    density_bonus = min(0.15, 0.05 * (len(signals) - 1))
    return round(min(1.0, weighted_total / weight_sum + density_bonus), 3)


def combined_score(fit: float, sig_score: float, icp: ICPConfig) -> float:
    return round(icp.icp_weight * fit + icp.signal_weight * sig_score, 3)


def prioritize(
    companies: list[Company],
    signals_by_company: dict[str, list[Signal]],
    icp: ICPConfig,
) -> list[ScoredAccount]:
    """Score and rank every company so reps always work the highest-
    propensity accounts first."""
    scored = []
    for company in companies:
        sigs = signals_by_company.get(company.id, [])
        fit = icp_fit(company, icp)
        sscore = signal_score(sigs, icp)
        scored.append(
            ScoredAccount(
                company=company,
                icp_fit=fit,
                signal_score=sscore,
                combined_score=combined_score(fit, sscore, icp),
                signals=sigs,
            )
        )
    return sorted(scored, key=lambda s: s.combined_score, reverse=True)

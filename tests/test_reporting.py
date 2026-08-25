from sdr_toolkit.models import Company, OutreachSequence, OutreachTouch, ProspectPackage, QualificationResult, ScoredAccount
from sdr_toolkit.reporting import build_funnel_metrics

COMPANY = Company("c1", "Acme", "acme.com", "ai", 100, "SF", "desc")


def _package(verdict, n_sequences=0):
    scored = ScoredAccount(COMPANY, icp_fit=0.8, signal_score=0.8, combined_score=0.8)
    qualification = QualificationResult("c1", verdict, "because", 0.8) if verdict else None
    sequences = {
        str(i): OutreachSequence(str(i), [OutreachTouch("email", 0, "s", "b")]) for i in range(n_sequences)
    }
    return ProspectPackage(scored, [], None, qualification, sequences)


def test_funnel_metrics_counts_by_verdict():
    packages = [
        _package("qualified", n_sequences=2),
        _package("qualified", n_sequences=1),
        _package("nurture"),
        _package(None),
    ]
    metrics = build_funnel_metrics(packages, signals_collected=10, elapsed_seconds=2.0)
    assert metrics.accounts_considered == 4
    assert metrics.accounts_nurture_or_better == 3
    assert metrics.accounts_qualified == 2
    assert metrics.sequences_drafted == 3
    assert metrics.qualification_rate == 0.5


def test_output_multiplier_is_positive_for_nonzero_qualified_accounts():
    packages = [_package("qualified", n_sequences=1)]
    metrics = build_funnel_metrics(packages, signals_collected=1, elapsed_seconds=1.0)
    assert metrics.output_multiplier > 0


def test_output_multiplier_zero_with_no_qualified_accounts():
    packages = [_package("disqualified")]
    metrics = build_funnel_metrics(packages, signals_collected=1, elapsed_seconds=1.0)
    assert metrics.manual_minutes_equivalent == 0
    assert metrics.output_multiplier == 0.0

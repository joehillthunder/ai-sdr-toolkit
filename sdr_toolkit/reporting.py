"""Funnel and output-per-rep reporting.

`estimate_output_multiplier` is deliberately conservative and documents
its assumption inline — the point isn't a precise ROI number, it's giving
a sales leader a concrete, falsifiable way to talk about "output per rep"
instead of a hand-wavy claim about AI making SDRs faster.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import ProspectPackage

# Conservative estimate of fully-manual minutes for one account: reading
# signals/context (5 min), writing a 3-touch personalized sequence (12 min).
# Override this if you have real rep time-tracking data.
MANUAL_MINUTES_PER_QUALIFIED_ACCOUNT = 17.0


@dataclass
class FunnelMetrics:
    accounts_considered: int
    signals_collected: int
    accounts_nurture_or_better: int
    accounts_qualified: int
    sequences_drafted: int
    elapsed_seconds: float

    @property
    def qualification_rate(self) -> float:
        return round(self.accounts_qualified / self.accounts_considered, 3) if self.accounts_considered else 0.0

    @property
    def manual_minutes_equivalent(self) -> float:
        return round(self.accounts_qualified * MANUAL_MINUTES_PER_QUALIFIED_ACCOUNT, 1)

    @property
    def output_multiplier(self) -> float:
        """How many times faster the pipeline qualified + drafted outreach
        for accounts vs. a rep doing the same work manually."""
        pipeline_minutes = self.elapsed_seconds / 60
        if pipeline_minutes <= 0:
            return 0.0
        return round(self.manual_minutes_equivalent / pipeline_minutes, 1)


def build_funnel_metrics(packages: list[ProspectPackage], signals_collected: int, elapsed_seconds: float) -> FunnelMetrics:
    nurture_or_better = [p for p in packages if p.qualification is not None]
    qualified = [p for p in packages if p.qualification and p.qualification.verdict == "qualified"]
    sequences = sum(len(p.sequences) for p in packages)
    return FunnelMetrics(
        accounts_considered=len(packages),
        signals_collected=signals_collected,
        accounts_nurture_or_better=len(nurture_or_better),
        accounts_qualified=len(qualified),
        sequences_drafted=sequences,
        elapsed_seconds=round(elapsed_seconds, 3),
    )

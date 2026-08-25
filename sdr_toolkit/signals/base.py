"""Signal source interface.

Every prospecting signal (hiring surges, funding events, tech-stack
adoption, website changes, ...) implements this interface. Ship a new
one — e.g. a real Crunchbase, BuiltWith, or LinkedIn Sales Navigator
adapter — by subclassing `SignalSource` and dropping it into the
orchestrator's source list. The rest of the pipeline (scoring, agents,
reporting) is source-agnostic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from ..models import Company, Signal


def recency_decay(detected_at: date, today: date, half_life_days: int = 30) -> float:
    """Exponential recency decay in [0, 1]. A signal from `half_life_days`
    ago is worth half as much as one from today."""
    days_since = max(0, (today - detected_at).days)
    return 0.5 ** (days_since / half_life_days)


class SignalSource(ABC):
    name: str = "signal_source"

    @abstractmethod
    def collect(self, companies: list[Company]) -> list[Signal]:
        """Return zero or more Signal objects for the given companies.

        Implementations should never raise on a single company failing
        to resolve (e.g. a network error fetching a website) — log and
        skip so one bad source doesn't take down a whole prospecting run.
        """
        raise NotImplementedError

"""Business development mode: long-cycle account research, partner
intelligence monitoring, technical opportunity assessment, and the
partnership-hypothesis chain (company -> signal -> opportunity ->
partner hypothesis -> target executive -> pitch -> next action).

Deliberately separate from sdr_toolkit's quota-driven SDR pipeline --
see the "Business development mode" section of the README for why.
"""

from .agents import AccountResearchAgent, PartnerIntelAgent, PartnershipHunterAgent, TechnicalBDAnalystAgent
from .models import (
    BDAccountDossier,
    PartnerAnnouncement,
    PartnershipOpportunity,
    PartnershipSignal,
    TechnicalAssessment,
)
from .partner_feeds import fetch_feed, parse_feed, watch_partners

__all__ = [
    "AccountResearchAgent",
    "PartnerIntelAgent",
    "PartnershipHunterAgent",
    "TechnicalBDAnalystAgent",
    "BDAccountDossier",
    "PartnerAnnouncement",
    "PartnershipOpportunity",
    "PartnershipSignal",
    "TechnicalAssessment",
    "fetch_feed",
    "parse_feed",
    "watch_partners",
]

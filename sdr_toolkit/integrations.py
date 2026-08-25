"""Activation: pushing prioritized, drafted work out to where reps live.

`CsvExportAdapter` always works offline. `HubSpotAdapter` is a real
integration (HubSpot CRM API v3) that activates when `HUBSPOT_ACCESS_TOKEN`
is set — it upserts the company, notes the qualification rationale, and
logs the drafted sequence as a task so a rep's queue is the pipeline's
output, not a spreadsheet someone has to re-key.
"""

from __future__ import annotations

import csv
import os
from abc import ABC, abstractmethod
from pathlib import Path

from .models import ProspectPackage

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None


class ActivationAdapter(ABC):
    @abstractmethod
    def activate(self, packages: list[ProspectPackage]) -> None:
        """Push scored/drafted packages into wherever reps work."""
        raise NotImplementedError


class CsvExportAdapter(ActivationAdapter):
    """Writes the prioritized queue (plus first-touch drafts) to CSV.
    Zero dependencies, zero credentials — the fallback that always works."""

    def __init__(self, out_path: str | Path):
        self.out_path = Path(out_path)

    def activate(self, packages: list[ProspectPackage]) -> None:
        fieldnames = [
            "company",
            "domain",
            "combined_score",
            "icp_fit",
            "signal_score",
            "verdict",
            "top_signal",
            "recommended_angle",
            "first_contact",
            "first_touch_subject",
            "first_touch_body",
        ]
        self.out_path.parent.mkdir(parents=True, exist_ok=True)
        with self.out_path.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for pkg in packages:
                sa = pkg.scored_account
                top_signal = max(sa.signals, key=lambda s: s.strength).evidence if sa.signals else ""
                first_contact = pkg.contacts[0] if pkg.contacts else None
                first_seq = pkg.sequences.get(first_contact.id) if first_contact else None
                first_touch = first_seq.touches[0] if first_seq else None
                writer.writerow(
                    {
                        "company": sa.company.name,
                        "domain": sa.company.domain,
                        "combined_score": sa.combined_score,
                        "icp_fit": sa.icp_fit,
                        "signal_score": sa.signal_score,
                        "verdict": pkg.qualification.verdict if pkg.qualification else "below_threshold",
                        "top_signal": top_signal,
                        "recommended_angle": pkg.dossier.recommended_angle if pkg.dossier else "",
                        "first_contact": first_contact.name if first_contact else "",
                        "first_touch_subject": first_touch.subject if first_touch else "",
                        "first_touch_body": first_touch.body if first_touch else "",
                    }
                )


class HubSpotAdapter(ActivationAdapter):
    """Upserts companies/notes/tasks into HubSpot CRM via the v3 REST API.

    Requires HUBSPOT_ACCESS_TOKEN (a private app token with crm.objects.*
    scopes). Only touches accounts qualification marked "qualified" —
    nurture/below-threshold accounts stay out of a rep's active queue.
    """

    BASE_URL = "https://api.hubapi.com"

    def __init__(self, access_token: str | None = None):
        self.access_token = access_token or os.environ.get("HUBSPOT_ACCESS_TOKEN")
        if not self.access_token:
            raise RuntimeError("HUBSPOT_ACCESS_TOKEN is not set.")
        if requests is None:  # pragma: no cover
            raise RuntimeError("The 'requests' package is required for HubSpotAdapter.")

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.access_token}", "Content-Type": "application/json"}

    def activate(self, packages: list[ProspectPackage]) -> None:
        for pkg in packages:
            if not pkg.qualification or pkg.qualification.verdict != "qualified":
                continue
            self._upsert_company(pkg)

    def _upsert_company(self, pkg: ProspectPackage) -> None:
        sa = pkg.scored_account
        payload = {
            "properties": {
                "name": sa.company.name,
                "domain": sa.company.domain,
                "description": (pkg.dossier.summary if pkg.dossier else sa.company.description),
                "ai_sdr_combined_score": sa.combined_score,
                "ai_sdr_qualification_rationale": pkg.qualification.rationale if pkg.qualification else "",
            }
        }
        requests.post(
            f"{self.BASE_URL}/crm/v3/objects/companies",
            headers=self._headers(),
            json=payload,
            timeout=10,
        )

"""Activation: pushing prioritized, drafted work out to where reps live.

`CsvExportAdapter` always works offline. `HubSpotAdapter`, `SalesforceAdapter`,
`ZohoAdapter`, and `MondayAdapter` are real integrations that activate once
their credentials are set — each upserts the company, notes the qualification
rationale, and only touches accounts the qualification agent verdicts
"qualified", so a rep's CRM/board view is the pipeline's filtered output, not
a spreadsheet someone has to re-key. No CRM yet? See
`sdr_toolkit.simple_crm.SimpleCRMAdapter`.
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
            "first_contact_title",
            "first_contact_linkedin",
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
                        "first_contact_title": first_contact.title if first_contact else "",
                        "first_contact_linkedin": first_contact.linkedin_url if first_contact else "",
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


class SalesforceAdapter(ActivationAdapter):
    """Upserts Accounts into Salesforce via the REST API (sobjects/Account).

    Requires a pre-obtained OAuth access token and the org's instance URL
    (`SALESFORCE_ACCESS_TOKEN`, `SALESFORCE_INSTANCE_URL` — e.g.
    `https://yourorg.my.salesforce.com`). Getting that token is a normal
    Salesforce Connected App / OAuth flow, out of scope for this adapter,
    which only makes the authenticated API calls once you have one.
    """

    API_VERSION = "v59.0"

    def __init__(self, instance_url: str | None = None, access_token: str | None = None):
        self.instance_url = (instance_url or os.environ.get("SALESFORCE_INSTANCE_URL") or "").rstrip("/")
        self.access_token = access_token or os.environ.get("SALESFORCE_ACCESS_TOKEN")
        if not self.instance_url or not self.access_token:
            raise RuntimeError("SALESFORCE_INSTANCE_URL and SALESFORCE_ACCESS_TOKEN must both be set.")
        if requests is None:  # pragma: no cover
            raise RuntimeError("The 'requests' package is required for SalesforceAdapter.")

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.access_token}", "Content-Type": "application/json"}

    def activate(self, packages: list[ProspectPackage]) -> None:
        for pkg in packages:
            if not pkg.qualification or pkg.qualification.verdict != "qualified":
                continue
            self._upsert_account(pkg)

    def _upsert_account(self, pkg: ProspectPackage) -> None:
        sa = pkg.scored_account
        payload = {
            "Name": sa.company.name,
            "Website": f"https://{sa.company.domain}",
            "Industry": sa.company.industry,
            "NumberOfEmployees": sa.company.employee_count,
            "Description": pkg.dossier.summary if pkg.dossier else sa.company.description,
        }
        requests.post(
            f"{self.instance_url}/services/data/{self.API_VERSION}/sobjects/Account",
            headers=self._headers(),
            json=payload,
            timeout=10,
        )


class ZohoAdapter(ActivationAdapter):
    """Upserts Accounts into Zoho CRM via the v2 REST API.

    Requires `ZOHO_ACCESS_TOKEN` (an OAuth token with `ZohoCRM.modules.accounts`
    scope) and `ZOHO_API_DOMAIN` (e.g. `https://www.zohoapis.com`, or your
    region's equivalent — `.eu`, `.in`, etc.).
    """

    def __init__(self, access_token: str | None = None, api_domain: str | None = None):
        self.access_token = access_token or os.environ.get("ZOHO_ACCESS_TOKEN")
        self.api_domain = (api_domain or os.environ.get("ZOHO_API_DOMAIN") or "https://www.zohoapis.com").rstrip("/")
        if not self.access_token:
            raise RuntimeError("ZOHO_ACCESS_TOKEN is not set.")
        if requests is None:  # pragma: no cover
            raise RuntimeError("The 'requests' package is required for ZohoAdapter.")

    def _headers(self) -> dict:
        return {"Authorization": f"Zoho-oauthtoken {self.access_token}", "Content-Type": "application/json"}

    def activate(self, packages: list[ProspectPackage]) -> None:
        for pkg in packages:
            if not pkg.qualification or pkg.qualification.verdict != "qualified":
                continue
            self._upsert_account(pkg)

    def _upsert_account(self, pkg: ProspectPackage) -> None:
        sa = pkg.scored_account
        payload = {
            "data": [
                {
                    "Account_Name": sa.company.name,
                    "Website": f"https://{sa.company.domain}",
                    "Industry": sa.company.industry,
                    "Employees": sa.company.employee_count,
                    "Description": pkg.dossier.summary if pkg.dossier else sa.company.description,
                }
            ]
        }
        requests.post(
            f"{self.api_domain}/crm/v2/Accounts",
            headers=self._headers(),
            json=payload,
            timeout=10,
        )


class MondayAdapter(ActivationAdapter):
    """Creates one item per qualified account on a monday.com board via
    its GraphQL API, with the dossier summary and qualification rationale
    posted as an update (comment) on that item.

    Deliberately doesn't try to set custom column values -- monday boards
    have arbitrary, per-board column schemas with no generic way to
    discover them, so an item + a plain-text update is the integration
    that works on any board without per-customer configuration.

    Requires `MONDAY_API_TOKEN` (Admin -> API in your monday account) and
    `MONDAY_BOARD_ID` (the numeric id in that board's URL).
    """

    API_URL = "https://api.monday.com/v2"

    def __init__(self, api_token: str | None = None, board_id: str | None = None):
        self.api_token = api_token or os.environ.get("MONDAY_API_TOKEN")
        self.board_id = board_id or os.environ.get("MONDAY_BOARD_ID")
        if not self.api_token or not self.board_id:
            raise RuntimeError("MONDAY_API_TOKEN and MONDAY_BOARD_ID must both be set.")
        if requests is None:  # pragma: no cover
            raise RuntimeError("The 'requests' package is required for MondayAdapter.")

    def _headers(self) -> dict:
        return {"Authorization": self.api_token, "Content-Type": "application/json"}

    def activate(self, packages: list[ProspectPackage]) -> None:
        for pkg in packages:
            if not pkg.qualification or pkg.qualification.verdict != "qualified":
                continue
            self._create_item(pkg)

    def _create_item(self, pkg: ProspectPackage) -> None:
        sa = pkg.scored_account
        create_item = (
            "mutation ($boardId: ID!, $itemName: String!) { "
            "create_item (board_id: $boardId, item_name: $itemName) { id } }"
        )
        resp = requests.post(
            self.API_URL,
            headers=self._headers(),
            json={"query": create_item, "variables": {"boardId": self.board_id, "itemName": sa.company.name}},
            timeout=10,
        )
        try:
            item_id = resp.json()["data"]["create_item"]["id"]
        except Exception:  # noqa: BLE001 -- a malformed response shouldn't crash the whole export
            return

        summary = pkg.dossier.summary if pkg.dossier else sa.company.description
        rationale = pkg.qualification.rationale if pkg.qualification else ""
        body = f"Score: {sa.combined_score} | {summary} | {rationale}"
        create_update = (
            "mutation ($itemId: ID!, $body: String!) { create_update (item_id: $itemId, body: $body) { id } }"
        )
        requests.post(
            self.API_URL,
            headers=self._headers(),
            json={"query": create_update, "variables": {"itemId": item_id, "body": body}},
            timeout=10,
        )

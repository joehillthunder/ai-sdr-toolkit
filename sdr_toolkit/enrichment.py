"""Contact enrichment — the "integrations" lead source for filling in
missing emails on accounts you already have (uploaded or AI-researched).

`HunterContactFinder` wraps Hunter.io's real Email Finder API
(https://hunter.io) — the same category of tool Clay/Apollo/ZoomInfo wrap
at much larger scale. Requires `HUNTER_API_KEY`; with no key it's simply
inert (`.available` is False) rather than raising, so enrichment is
always an optional, additive step, never a hard dependency of a run.
"""

from __future__ import annotations

import os

from .models import Company, Contact

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None


class HunterContactFinder:
    BASE_URL = "https://api.hunter.io/v2"

    def __init__(self, api_key: str | None = None, timeout: float = 8.0):
        self.api_key = api_key or os.environ.get("HUNTER_API_KEY")
        self.timeout = timeout

    @property
    def available(self) -> bool:
        return bool(self.api_key) and requests is not None

    def find_email(self, domain: str, full_name: str | None = None) -> dict | None:
        """One lookup. Returns {"email": ..., "confidence": ...} or None."""
        if not self.available:
            return None
        params = {"domain": domain, "api_key": self.api_key}
        if full_name:
            parts = full_name.split()
            if len(parts) >= 2:
                params["first_name"], params["last_name"] = parts[0], parts[-1]
        try:
            resp = requests.get(f"{self.BASE_URL}/email-finder", params=params, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json().get("data") or {}
        except Exception:  # noqa: BLE001 -- enrichment failing should never break a run
            return None
        email = data.get("email")
        if not email:
            return None
        return {"email": email, "confidence": data.get("score")}

    def enrich_contacts(
        self, companies: list[Company], contacts_by_company: dict[str, list[Contact]]
    ) -> int:
        """Fill in missing `Contact.email` fields in place. Returns the
        number of contacts successfully enriched."""
        if not self.available:
            return 0
        enriched = 0
        for company in companies:
            for contact in contacts_by_company.get(company.id, []):
                if contact.email:
                    continue
                result = self.find_email(company.domain, contact.name)
                if result:
                    contact.email = result["email"]
                    enriched += 1
        return enriched

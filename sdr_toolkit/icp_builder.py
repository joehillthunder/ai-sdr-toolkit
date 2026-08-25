"""Turn a company's own website + a plain-language description of who
they sell to into an ICPConfig — the "give your guess of an ideal
customer" step, so a non-technical user never has to hand-edit YAML.

Offline (`MockLLMClient`) mode returns a generic, reasonable-default ICP
so the wizard still works end to end with no API key; live mode asks the
configured model to actually read the site copy and the user's
description and propose real targeting criteria.
"""

from __future__ import annotations

from .config import ICPConfig
from .llm import LLMClient
from .text import parse_labeled, split_csv_field, strip_html

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

SYSTEM = (
    "You are a B2B go-to-market strategist building an Ideal Customer Profile "
    "(ICP) from a company's own website copy and their plain-language description "
    "of who they sell to. Be specific and practical, not generic. Respond ONLY in "
    "this exact labeled format:\n"
    "INDUSTRIES: <comma-separated, 2-5 target industries, lowercase, short>\n"
    "MIN_EMPLOYEES: <integer>\n"
    "MAX_EMPLOYEES: <integer>\n"
    "DESCRIPTION_KEYWORDS: <comma-separated, 4-8 words likely in a good-fit "
    "company's own description>\n"
    "HIRING_KEYWORDS: <comma-separated job titles/roles a good-fit company would "
    "be hiring for right now>\n"
    "TECH_KEYWORDS: <comma-separated technologies/terms a good-fit company might "
    "mention adopting>\n"
    "WEBSITE_KEYWORDS: <comma-separated phrases a good-fit company's own homepage "
    "might use>"
)

_KEYS = [
    "INDUSTRIES",
    "MIN_EMPLOYEES",
    "MAX_EMPLOYEES",
    "DESCRIPTION_KEYWORDS",
    "HIRING_KEYWORDS",
    "TECH_KEYWORDS",
    "WEBSITE_KEYWORDS",
]


def fetch_url_text(url: str, timeout: float = 6.0, max_chars: int = 3500) -> str:
    """Best-effort fetch + de-tag a webpage. Returns "" on any failure —
    this is a convenience input to an LLM prompt, not something that
    should ever crash a run."""
    if requests is None:
        return ""
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    try:
        resp = requests.get(url, timeout=timeout, headers={"User-Agent": "ai-sdr-toolkit/0.1"})
        resp.raise_for_status()
        return strip_html(resp.text, max_chars=max_chars)
    except Exception:
        return ""


def _int(value: str, default: int) -> int:
    try:
        return int("".join(ch for ch in value if ch.isdigit()))
    except (ValueError, TypeError):
        return default


def build_icp(
    llm: LLMClient,
    company_name: str,
    website_texts: list[str],
    ideal_customer_description: str,
    name: str | None = None,
) -> ICPConfig:
    defaults = ICPConfig.default()

    site_context = "\n\n---\n\n".join(t for t in website_texts if t) or "(no website text available)"
    prompt = (
        f"Company: {company_name}\n\n"
        f"Their own website copy:\n{site_context}\n\n"
        f"Their description of who they sell to, in their own words:\n"
        f"{ideal_customer_description or '(not provided)'}\n\n"
        "Propose the ICP now."
    )
    raw = llm.generate(SYSTEM, prompt)
    parsed = parse_labeled(raw, _KEYS)

    industries = split_csv_field(parsed["INDUSTRIES"]) or defaults.target_industries
    description_keywords = split_csv_field(parsed["DESCRIPTION_KEYWORDS"]) or defaults.description_keywords
    hiring_keywords = split_csv_field(parsed["HIRING_KEYWORDS"]) or defaults.signal_keywords.get("hiring_surge", [])
    tech_keywords = split_csv_field(parsed["TECH_KEYWORDS"]) or defaults.signal_keywords.get("tech_adoption", [])
    website_keywords = split_csv_field(parsed["WEBSITE_KEYWORDS"]) or defaults.signal_keywords.get("website_change", [])

    return ICPConfig(
        name=name or f"{company_name} — generated ICP",
        target_industries=industries,
        min_employees=_int(parsed["MIN_EMPLOYEES"], defaults.min_employees),
        max_employees=_int(parsed["MAX_EMPLOYEES"], defaults.max_employees),
        description_keywords=description_keywords,
        signal_keywords={
            "hiring_surge": hiring_keywords,
            "tech_adoption": tech_keywords,
            "website_change": website_keywords,
        },
        signal_type_weights=defaults.signal_type_weights,
        icp_weight=defaults.icp_weight,
        signal_weight=defaults.signal_weight,
        qualification_threshold=defaults.qualification_threshold,
        nurture_threshold=defaults.nurture_threshold,
    )

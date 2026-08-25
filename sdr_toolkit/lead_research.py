"""Research-assisted lead discovery — the "research" lead source.

This is deliberately NOT a live company database. It asks the configured
model to brainstorm real companies it's aware of that plausibly match an
ICP, from its training knowledge. Every result is returned with
`verified: False` and is meant to be checked by a human before it goes
anywhere near an outbound queue — models are fluent, not omniscient, and
will occasionally suggest a company that's the wrong size, defunct, or
simply made up.

For actual verified firmographic data at scale, see the "integrations"
lead source (`sdr_toolkit/enrichment.py`, and the `SignalSource`
interface for a real data provider like Clay/Apollo/Crunchbase).
"""

from __future__ import annotations

from .config import ICPConfig
from .llm import LLMClient

SYSTEM = (
    "You are a market researcher brainstorming real companies that plausibly "
    "match an Ideal Customer Profile, based on your training knowledge. You are "
    "not a live database and may be wrong or out of date, so only suggest "
    "companies you have real information about, and keep the reasons honest and "
    "specific rather than generic. Respond ONLY as a numbered list, one company "
    "per line, in this exact format:\n"
    "1. <Company Name> — <one-line reason it plausibly fits>\n"
    "2. <Company Name> — <one-line reason it plausibly fits>\n"
    "...continue up to the requested count."
)


def suggest_candidate_companies(
    llm: LLMClient, icp: ICPConfig, count: int = 8, region: str = ""
) -> list[dict]:
    prompt = (
        f"ICP: {icp.name}\n"
        f"Target industries: {', '.join(icp.target_industries) or 'unspecified'}\n"
        f"Employee range: {icp.min_employees}-{icp.max_employees}\n"
        f"Good-fit description keywords: {', '.join(icp.description_keywords) or 'unspecified'}\n"
        f"Region constraint: {region or 'none'}\n\n"
        f"List {count} real companies you're aware of that plausibly fit this ICP."
    )
    raw = llm.generate(SYSTEM, prompt)

    results: list[dict] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or not line[0].isdigit():
            continue
        after_number = line.split(".", 1)[1].strip() if "." in line else line
        if "—" in after_number:
            name, reason = after_number.split("—", 1)
        elif " - " in after_number:
            name, reason = after_number.split(" - ", 1)
        else:
            name, reason = after_number, ""
        name = name.strip()
        if name:
            results.append({"name": name, "reason": reason.strip(), "source": "ai_research", "verified": False})
    return results[:count]

"""Small text helpers shared by agents.py and icp_builder.py."""

from __future__ import annotations

import re


def parse_labeled(text: str, keys: list[str]) -> dict[str, str]:
    """Parse `KEY: value` (possibly multi-line, until the next known key)
    blocks out of an LLM response."""
    result: dict[str, str] = {k: "" for k in keys}
    current = None
    for line in text.splitlines():
        stripped = line.strip()
        matched_key = None
        for k in keys:
            if stripped.upper().startswith(f"{k}:"):
                matched_key = k
                break
        if matched_key:
            current = matched_key
            result[current] = stripped[len(matched_key) + 1 :].strip()
        elif current:
            result[current] = (result[current] + " " + stripped).strip()
    return result


def split_csv_field(value: str) -> list[str]:
    """Split a comma-separated LLM field into a clean list of lowercase terms."""
    return [v.strip().lower() for v in value.split(",") if v.strip()]


_TAG_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
_ANY_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def strip_html(html: str, max_chars: int = 4000) -> str:
    """Cheap, dependency-free HTML-to-text for feeding page copy to an LLM.
    Not a real parser -- good enough for "what does this homepage say"."""
    text = _TAG_RE.sub(" ", html)
    text = _ANY_TAG_RE.sub(" ", text)
    text = _WS_RE.sub(" ", text).strip()
    return text[:max_chars]

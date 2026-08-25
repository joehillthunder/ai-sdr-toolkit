"""Partner intelligence: watch named companies' own newsroom/blog RSS or
Atom feeds and flag announcements that create a partnership opening.

This deliberately uses each company's own public feed rather than
scraping or a paid news API -- it's free, it's not a ToS problem (it's
literally what RSS is for), and it works for any company that publishes
one, which most do for press releases and engineering blogs.

`fetch_feed` / `parse_feed` are split so parsing is testable against a
fixed XML string with no network involved; `watch_partners` is the
orchestration a CLI or the wizard calls.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import date, datetime
from email.utils import parsedate_to_datetime

from ..llm import LLMClient
from ..text import strip_html
from .agents import PartnerIntelAgent
from .models import PartnerAnnouncement, PartnershipSignal

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None


def _local(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def _parse_date(text: str | None) -> date | None:
    if not text:
        return None
    text = text.strip()
    try:
        return parsedate_to_datetime(text).date()
    except (TypeError, ValueError):
        pass
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def parse_feed(xml_text: str, company: str, max_items: int = 8) -> list[PartnerAnnouncement]:
    """Parse RSS 2.0 `<item>` or Atom `<entry>` elements, namespace-agnostic."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    entries = [el for el in root.iter() if _local(el.tag) in ("item", "entry")]
    results: list[PartnerAnnouncement] = []
    for el in entries[:max_items]:
        children = {_local(c.tag): c for c in el}

        title_el = children.get("title")
        title = (title_el.text or "").strip() if title_el is not None and title_el.text else ""

        link = ""
        link_el = children.get("link")
        if link_el is not None:
            link = (link_el.get("href") or link_el.text or "").strip()

        # NB: `or`-chaining Elements is a trap -- a leaf Element (no child
        # elements of its own) is falsy in boolean context even with real
        # text, which would silently skip a populated <pubDate> etc.
        summary_el = children.get("description")
        if summary_el is None:
            summary_el = children.get("summary")
        if summary_el is None:
            summary_el = children.get("content")
        summary = strip_html(summary_el.text, max_chars=600) if summary_el is not None and summary_el.text else ""

        pub_el = children.get("pubDate")
        if pub_el is None:
            pub_el = children.get("updated")
        if pub_el is None:
            pub_el = children.get("published")
        published_at = _parse_date(pub_el.text if pub_el is not None else None)

        if title:
            results.append(
                PartnerAnnouncement(company=company, title=title, url=link, published_at=published_at, summary=summary)
            )
    return results


def fetch_feed(url: str, timeout: float = 8.0) -> str:
    if requests is None:
        return ""
    try:
        resp = requests.get(url, timeout=timeout, headers={"User-Agent": "ai-sdr-toolkit-bd/0.1"})
        resp.raise_for_status()
        return resp.text
    except Exception:  # noqa: BLE001 -- one bad feed should never break a watch run
        return ""


def watch_partners(
    llm: LLMClient,
    feeds: dict[str, str],
    topics: list[str],
    max_items_per_feed: int = 5,
) -> list[PartnershipSignal]:
    """Fetch every watched company's feed, keep only the announcements
    the model judges create a real partnership opening against `topics`."""
    agent = PartnerIntelAgent(llm)
    signals: list[PartnershipSignal] = []
    for company, url in feeds.items():
        xml_text = fetch_feed(url)
        if not xml_text:
            continue
        for announcement in parse_feed(xml_text, company, max_items=max_items_per_feed):
            signal = agent.evaluate(announcement, topics)
            if signal:
                signals.append(signal)
    return signals

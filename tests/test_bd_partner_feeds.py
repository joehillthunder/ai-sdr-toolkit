from datetime import date
from unittest.mock import patch

from sdr_toolkit.bd.partner_feeds import fetch_feed, parse_feed, watch_partners
from sdr_toolkit.llm import MockLLMClient

RSS_SAMPLE = """<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <title>Acme Newsroom</title>
    <item>
      <title>Acme launches AI PC lineup</title>
      <link>https://acme.example/news/ai-pc</link>
      <description>&lt;p&gt;New on-device inference capability across the lineup.&lt;/p&gt;</description>
      <pubDate>Mon, 01 Jan 2024 12:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Acme reports quarterly earnings</title>
      <link>https://acme.example/news/earnings</link>
      <description>Standard quarterly filing, nothing product-related.</description>
      <pubDate>Tue, 02 Jan 2024 12:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>"""

ATOM_SAMPLE = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Acme Engineering Blog</title>
  <entry>
    <title>Spatial computing display SDK released</title>
    <link href="https://acme.example/blog/spatial-sdk"/>
    <summary>A new SDK for building spatial computing interfaces.</summary>
    <updated>2024-02-01T10:00:00Z</updated>
  </entry>
</feed>"""


def test_parse_feed_handles_rss_items():
    results = parse_feed(RSS_SAMPLE, company="Acme")
    assert len(results) == 2
    first = results[0]
    assert first.company == "Acme"
    assert first.title == "Acme launches AI PC lineup"
    assert first.url == "https://acme.example/news/ai-pc"
    assert first.published_at == date(2024, 1, 1)
    assert "on-device inference" in first.summary.lower()


def test_parse_feed_handles_atom_entries():
    results = parse_feed(ATOM_SAMPLE, company="Acme")
    assert len(results) == 1
    entry = results[0]
    assert entry.title == "Spatial computing display SDK released"
    assert entry.url == "https://acme.example/blog/spatial-sdk"
    assert entry.published_at == date(2024, 2, 1)


def test_parse_feed_survives_malformed_xml():
    assert parse_feed("<not><valid", company="Acme") == []


def test_parse_feed_respects_max_items():
    results = parse_feed(RSS_SAMPLE, company="Acme", max_items=1)
    assert len(results) == 1


def test_fetch_feed_survives_network_failure():
    with patch("sdr_toolkit.bd.partner_feeds.requests") as mock_requests:
        mock_requests.get.side_effect = Exception("network down")
        assert fetch_feed("https://acme.example/rss") == ""


def test_watch_partners_returns_only_relevant_signals():
    with patch("sdr_toolkit.bd.partner_feeds.requests") as mock_requests:
        mock_requests.get.return_value.raise_for_status = lambda: None
        mock_requests.get.return_value.text = RSS_SAMPLE

        signals = watch_partners(
            MockLLMClient(), feeds={"Acme": "https://acme.example/rss"}, topics=["ai pcs", "local inference"]
        )

    assert len(signals) == 2  # MockLLMClient's canned response marks both relevant
    assert all(s.announcement.company == "Acme" for s in signals)


def test_watch_partners_skips_feeds_that_fail_to_fetch():
    with patch("sdr_toolkit.bd.partner_feeds.requests") as mock_requests:
        mock_requests.get.side_effect = Exception("dns failure")
        signals = watch_partners(MockLLMClient(), feeds={"Acme": "https://acme.example/rss"}, topics=["ai pcs"])
    assert signals == []

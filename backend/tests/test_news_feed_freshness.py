"""News injected into decision prompts must be fresh and age-labeled.

2026-07-06 evidence: a "BTC dips below $63K amid ETF outflows" article was
re-injected verbatim into every 15-minute decision cycle for 4+ hours while
spot had already moved to $61.7k and was recovering. The stateless LLM
re-anchored on the stale narrative each cycle (embellishing it along the way:
"8th consecutive day" drifted to "8th consecutive week") and sold a local
bottom five times. Stale context is the hallucination vector here - the fix
is at the source: filter by age and make every item's age explicit.
"""
from __future__ import annotations

import datetime as dt
from email.utils import format_datetime

from services import news_feed


def _rss(items: str) -> bytes:
    return f"""<?xml version="1.0"?>
<rss version="2.0"><channel><title>t</title>{items}</channel></rss>""".encode()


def _item(title: str, published: dt.datetime) -> str:
    return (
        f"<item><title>{title}</title>"
        f"<pubDate>{format_datetime(published)}</pubDate>"
        f"<description>{title} body</description></item>"
    )


NOW = dt.datetime(2026, 7, 6, 15, 0, 0, tzinfo=dt.timezone.utc)


class _FakeResponse:
    status_code = 200

    def __init__(self, content: bytes):
        self.content = content


def _patch_feed(monkeypatch, xml: bytes):
    monkeypatch.setattr(news_feed.requests, "get", lambda *a, **k: _FakeResponse(xml))


def test_stale_items_filtered_out(monkeypatch):
    xml = _rss(
        _item("fresh news", NOW - dt.timedelta(hours=2))
        + _item("stale narrative", NOW - dt.timedelta(hours=30))
    )
    _patch_feed(monkeypatch, xml)

    text = news_feed.fetch_latest_news(now=NOW)
    assert "fresh news" in text
    assert "stale narrative" not in text


def test_items_carry_relative_age_label(monkeypatch):
    xml = _rss(_item("fresh news", NOW - dt.timedelta(hours=3)))
    _patch_feed(monkeypatch, xml)

    text = news_feed.fetch_latest_news(now=NOW)
    assert "3.0h ago" in text


def test_undated_items_kept_but_flagged(monkeypatch):
    xml = _rss("<item><title>undated piece</title><description>x</description></item>")
    _patch_feed(monkeypatch, xml)

    text = news_feed.fetch_latest_news(now=NOW)
    assert "undated piece" in text
    assert "age unknown" in text


def test_custom_max_age(monkeypatch):
    xml = _rss(_item("six hours old", NOW - dt.timedelta(hours=6)))
    _patch_feed(monkeypatch, xml)

    assert "six hours old" not in news_feed.fetch_latest_news(now=NOW, max_age_hours=4)
    assert "six hours old" in news_feed.fetch_latest_news(now=NOW, max_age_hours=12)

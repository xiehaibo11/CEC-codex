import logging
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from typing import List, Optional
import xml.etree.ElementTree as ET

import requests


logger = logging.getLogger(__name__)

NEWS_FEED_URL = "https://coinjournal.net/news/feed/"

# Items older than this never reach a decision prompt. 2026-07-06: a stale
# "BTC dips below $63K" article re-anchored the LLM every 15-minute cycle for
# 4+ hours while spot had already moved on - five losing same-narrative sells.
DEFAULT_MAX_AGE_HOURS = 24.0


def _strip_html_tags(text: str) -> str:
    if not text:
        return ""
    cleaned = unescape(text)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def fetch_latest_news(
    max_chars: int = 4000,
    *,
    max_age_hours: float = DEFAULT_MAX_AGE_HOURS,
    now: Optional[datetime] = None,
) -> str:
    """Fresh news only, every item prefixed with its age.

    Age filtering + explicit "[N.Nh ago]" labels keep a stateless decision
    loop from re-anchoring on yesterday's narrative as if it just happened."""
    try:
        response = requests.get(NEWS_FEED_URL, timeout=10)
        if response.status_code != 200:
            logger.warning("Failed to fetch news feed: status %s", response.status_code)
            return ""

        root = ET.fromstring(response.content)
        channel = root.find("channel")
        if channel is None:
            return ""

        resolved_now = now or datetime.now(timezone.utc)
        entries: List[str] = []

        for item in channel.findall("item"):
            title = _strip_html_tags(item.findtext("title") or "")
            pub_date_raw = (item.findtext("pubDate") or "").strip()
            summary_raw = item.findtext("description") or ""

            summary = _strip_html_tags(summary_raw)
            summary = re.sub(r"The post .*? appeared first on .*", "", summary, flags=re.IGNORECASE).strip()

            formatted_time = pub_date_raw
            age_label = "age unknown"
            if pub_date_raw:
                try:
                    parsed = parsedate_to_datetime(pub_date_raw)
                    if parsed is not None:
                        if parsed.tzinfo is None:
                            parsed = parsed.replace(tzinfo=timezone.utc)
                        else:
                            parsed = parsed.astimezone(timezone.utc)
                        age_hours = (resolved_now - parsed).total_seconds() / 3600
                        if age_hours > max_age_hours:
                            continue
                        formatted_time = parsed.strftime("%Y-%m-%d %H:%M:%SZ")
                        age_label = f"{max(age_hours, 0):.1f}h ago"
                except Exception:  # noqa: BLE001
                    formatted_time = pub_date_raw
            formatted_time = f"[{age_label}] {formatted_time}".strip()

            parts = []
            if formatted_time:
                parts.append(formatted_time)
            if title:
                parts.append(title)

            entry_text = " | ".join(parts)
            if summary:
                entry_text = f"{entry_text}: {summary}" if entry_text else summary

            entry_text = entry_text.strip()
            if not entry_text:
                continue

            existing_text = "\n".join(entries)
            candidate_text = f"{existing_text}\n{entry_text}" if existing_text else entry_text
            if len(candidate_text) > max_chars:
                remaining = max_chars - len(existing_text)
                if existing_text:
                    remaining -= 1
                if remaining <= 0:
                    break
                truncated = entry_text[:remaining].rstrip()
                if truncated:
                    if len(truncated) < len(entry_text):
                        truncated = truncated.rstrip(" .,;:-") + "..."
                    entries.append(truncated)
                break

            entries.append(entry_text)

        return "\n".join(entries)

    except Exception as err:  # noqa: BLE001
        logger.warning("Failed to process news feed: %s", err)
        return ""

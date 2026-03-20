from __future__ import annotations

from email.utils import parsedate_to_datetime
import html
import re
import urllib.request
import xml.etree.ElementTree as ET

from ..models import NewsWindow, RawNewsItem
from ..utils import compact_whitespace, parse_iso_datetime, stable_id
from .base import SourceAdapter


def _strip_html(text: str) -> str:
    return compact_whitespace(re.sub(r"<[^>]+>", " ", html.unescape(text or "")))


def _normalize_published_at(value: str, fallback: str) -> str:
    candidate = (value or "").strip()
    parsed = parse_iso_datetime(candidate)
    if parsed is not None:
        return parsed.isoformat().replace("+00:00", "Z")
    try:
        parsed = parsedate_to_datetime(candidate)
        return parsed.isoformat().replace("+00:00", "Z")
    except (TypeError, ValueError):
        return fallback


class RSSSourceAdapter(SourceAdapter):
    def fetch(self, window: NewsWindow, collected_at: str) -> list[RawNewsItem]:
        request = urllib.request.Request(
            self.definition.endpoint,
            headers={"User-Agent": "news-employee/0.1"},
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = response.read()

        root = ET.fromstring(payload)
        items = []
        window_start = parse_iso_datetime(window.start)
        window_end = parse_iso_datetime(window.end)
        entries = root.findall('.//item') or root.findall('.//{http://www.w3.org/2005/Atom}entry')
        for entry in entries:
            title = (
                entry.findtext('title')
                or entry.findtext('{http://www.w3.org/2005/Atom}title')
                or ''
            )
            summary = (
                entry.findtext('description')
                or entry.findtext('summary')
                or entry.findtext('{http://www.w3.org/2005/Atom}summary')
                or ''
            )
            published_at = (
                entry.findtext('pubDate')
                or entry.findtext('published')
                or entry.findtext('{http://www.w3.org/2005/Atom}updated')
                or collected_at
            )
            published_at = _normalize_published_at(published_at, collected_at)
            published_dt = parse_iso_datetime(published_at)
            if (
                published_dt is not None
                and window_start is not None
                and window_end is not None
                and not (window_start <= published_dt <= window_end)
            ):
                continue
            link = entry.findtext('link') or ''
            if not link:
                atom_link = entry.find('{http://www.w3.org/2005/Atom}link')
                if atom_link is not None:
                    link = atom_link.attrib.get('href', '')
            items.append(
                RawNewsItem(
                    id=stable_id(self.definition.name, title, link, size=16),
                    source=self.definition.name,
                    source_type='rss',
                    source_tier=self.definition.tier,
                    language=self.definition.language,
                    title=_strip_html(title),
                    summary=_strip_html(summary),
                    url=link,
                    published_at=published_at,
                    collected_at=collected_at,
                    tags=list(self.definition.tags),
                    metadata={"window_start": window.start, "window_end": window.end},
                )
            )
        return items

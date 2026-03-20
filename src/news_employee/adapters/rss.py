from __future__ import annotations

import html
import re
import urllib.request
import xml.etree.ElementTree as ET

from ..models import NewsWindow, RawNewsItem
from ..utils import compact_whitespace, stable_id
from .base import SourceAdapter


def _strip_html(text: str) -> str:
    return compact_whitespace(re.sub(r"<[^>]+>", " ", html.unescape(text or "")))


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
        entries = root.findall(".//item") or root.findall(".//{http://www.w3.org/2005/Atom}entry")
        for entry in entries:
            title = (
                entry.findtext("title")
                or entry.findtext("{http://www.w3.org/2005/Atom}title")
                or ""
            )
            summary = (
                entry.findtext("description")
                or entry.findtext("summary")
                or entry.findtext("{http://www.w3.org/2005/Atom}summary")
                or ""
            )
            published_at = (
                entry.findtext("pubDate")
                or entry.findtext("published")
                or entry.findtext("{http://www.w3.org/2005/Atom}updated")
                or collected_at
            )
            link = entry.findtext("link") or ""
            if not link:
                atom_link = entry.find("{http://www.w3.org/2005/Atom}link")
                if atom_link is not None:
                    link = atom_link.attrib.get("href", "")
            items.append(
                RawNewsItem(
                    id=stable_id(self.definition.name, title, link, size=16),
                    source=self.definition.name,
                    source_type="rss",
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

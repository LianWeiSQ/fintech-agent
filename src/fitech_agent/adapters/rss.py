from __future__ import annotations

from email.utils import parsedate_to_datetime
import html
import re
import urllib.request
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

from ..models import NewsWindow, RawNewsItem
from ..utils import compact_whitespace, parse_iso_datetime, stable_id
from .base import SourceAdapter, build_source_metadata

ATOM_NS = "{http://www.w3.org/2005/Atom}"
DC_CREATOR_NS = "{http://purl.org/dc/elements/1.1/}creator"
HREF_RE = re.compile(r"""href=["']([^"']+)["']""", re.IGNORECASE)


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


def _normalize_token(value: str) -> str:
    return compact_whitespace((value or "").strip()).lower()


def _coerce_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw_items = value.split(",")
    elif isinstance(value, (list, tuple, set)):
        raw_items = [str(item) for item in value]
    else:
        raw_items = [str(value)]
    return [item for item in (compact_whitespace(raw).strip() for raw in raw_items) if item]


def _text_contains_any(text: str, keywords: list[str]) -> bool:
    normalized_text = _normalize_token(text)
    if not normalized_text:
        return False
    return any(
        keyword_token in normalized_text
        for keyword_token in (_normalize_token(keyword) for keyword in keywords)
        if keyword_token
    )


def _domain_matches(url: str, domains: list[str]) -> bool:
    if not url or not domains:
        return False
    host = urlparse(url).netloc.lower()
    if not host:
        return False
    for domain in domains:
        candidate = domain.strip().lower()
        if not candidate:
            continue
        if host == candidate or host.endswith(f".{candidate}") or candidate in host:
            return True
    return False


def _extract_author(entry: ET.Element) -> str:
    for tag in ("author", DC_CREATOR_NS):
        author = _strip_html(entry.findtext(tag) or "")
        if author:
            return author

    atom_author = entry.find(f"{ATOM_NS}author")
    if atom_author is not None:
        author = _strip_html(
            atom_author.findtext(f"{ATOM_NS}name")
            or atom_author.text
            or ""
        )
        if author:
            return author
    return ""


def _extract_summary_links(summary: str) -> list[str]:
    seen: set[str] = set()
    links: list[str] = []
    for match in HREF_RE.findall(summary or ""):
        candidate = match.strip()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        links.append(candidate)
    return links


def _extract_link(entry: ET.Element) -> str:
    link = (entry.findtext("link") or "").strip()
    if link:
        return link

    atom_links = entry.findall(f"{ATOM_NS}link")
    if not atom_links:
        return ""
    for atom_link in atom_links:
        rel = (atom_link.attrib.get("rel") or "").strip().lower()
        href = (atom_link.attrib.get("href") or "").strip()
        if href and rel in {"", "alternate"}:
            return href
    return (atom_links[0].attrib.get("href") or "").strip()


def _matches_filters(
    definition_metadata: dict[str, object],
    *,
    title: str,
    summary: str,
    link: str,
    author: str,
    summary_links: list[str],
) -> bool:
    author_allowlist = _coerce_list(definition_metadata.get("author_allowlist"))
    title_allowlist_keywords = _coerce_list(
        definition_metadata.get("title_allowlist_keywords")
    )
    title_blocklist_keywords = _coerce_list(
        definition_metadata.get("title_blocklist_keywords")
    )
    link_allowlist_domains = _coerce_list(
        definition_metadata.get("link_allowlist_domains")
    )
    summary_href_allowlist_domains = _coerce_list(
        definition_metadata.get("summary_href_allowlist_domains")
    )
    combined_text = " ".join(part for part in (title, summary) if part)
    normalized_author = _normalize_token(author)

    if author_allowlist and not any(
        allowed in normalized_author or normalized_author in allowed
        for allowed in (_normalize_token(item) for item in author_allowlist)
        if allowed and normalized_author
    ):
        return False
    if title_allowlist_keywords and not _text_contains_any(
        combined_text,
        title_allowlist_keywords,
    ):
        return False
    if title_blocklist_keywords and _text_contains_any(
        combined_text,
        title_blocklist_keywords,
    ):
        return False
    if link_allowlist_domains and not _domain_matches(link, link_allowlist_domains):
        return False
    if summary_href_allowlist_domains and not any(
        _domain_matches(item, summary_href_allowlist_domains)
        for item in summary_links
    ):
        return False
    return True


class RSSSourceAdapter(SourceAdapter):
    def fetch(self, window: NewsWindow, collected_at: str) -> list[RawNewsItem]:
        request = urllib.request.Request(
            self.definition.endpoint,
            headers={"User-Agent": "fitech-agent/0.1"},
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = response.read()

        root = ET.fromstring(payload)
        items = []
        window_start = parse_iso_datetime(window.start)
        window_end = parse_iso_datetime(window.end)
        entries = root.findall(".//item") or root.findall(f".//{ATOM_NS}entry")
        for entry in entries:
            title = (
                entry.findtext("title")
                or entry.findtext(f"{ATOM_NS}title")
                or ""
            )
            raw_summary = (
                entry.findtext("description")
                or entry.findtext("summary")
                or entry.findtext(f"{ATOM_NS}summary")
                or ""
            )
            summary = _strip_html(raw_summary)
            published_at = (
                entry.findtext("pubDate")
                or entry.findtext("published")
                or entry.findtext(f"{ATOM_NS}updated")
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

            link = _extract_link(entry)
            author = _extract_author(entry)
            summary_links = _extract_summary_links(raw_summary)
            if not _matches_filters(
                self.definition.metadata,
                title=title,
                summary=summary,
                link=link,
                author=author,
                summary_links=summary_links,
            ):
                continue

            items.append(
                RawNewsItem(
                    id=stable_id(self.definition.name, title, link, size=16),
                    source=self.definition.name,
                    source_type="rss",
                    source_tier=self.definition.tier,
                    language=self.definition.language,
                    title=_strip_html(title),
                    summary=summary,
                    url=link,
                    published_at=published_at,
                    collected_at=collected_at,
                    tags=list(self.definition.tags),
                    metadata=build_source_metadata(
                        self.definition,
                        {
                            "entry_author": author,
                            "summary_links": summary_links,
                            "window_start": window.start,
                            "window_end": window.end,
                        },
                    ),
                )
            )
        return items

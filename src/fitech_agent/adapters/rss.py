from __future__ import annotations

import html
import os
import re
import ssl
import time
import urllib.request
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin, urlparse
import xml.etree.ElementTree as ET

from ..models import NewsWindow, RawNewsItem
from ..utils import compact_whitespace, parse_iso_datetime, stable_id
from .base import SourceAdapter, build_source_metadata

ATOM_NS = "{http://www.w3.org/2005/Atom}"
DC_CREATOR_NS = "{http://purl.org/dc/elements/1.1/}creator"
HREF_RE = re.compile(r"""href=["']([^"']+)["']""", re.IGNORECASE)
ABSOLUTE_URL_RE = re.compile(r"^[a-z][a-z0-9+.-]*://", re.IGNORECASE)
BARE_HOST_RE = re.compile(r"^(?:www\.)?[a-z0-9.-]+\.[a-z]{2,}(?:[/:?#].*)?$", re.IGNORECASE)

DEFAULT_TIMEOUT_SECONDS = 20.0
DEFAULT_RETRY_ATTEMPTS = 2
DEFAULT_RETRY_BACKOFF_SECONDS = 1.0
DEFAULT_REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*;q=0.8",
}


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


def _coerce_float(value: object, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _coerce_int(value: object, default: int) -> int:
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return default


def _coerce_bool(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    normalized = compact_whitespace(str(value)).lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _text_contains_any(text: str, keywords: list[str]) -> bool:
    normalized_text = _normalize_token(text)
    if not normalized_text:
        return False
    return any(
        keyword_token in normalized_text
        for keyword_token in (_normalize_token(keyword) for keyword in keywords)
        if keyword_token
    )


def _normalize_url(url: str, base_url: str = "") -> str:
    candidate = compact_whitespace(html.unescape(url or ""))
    if not candidate:
        return ""
    if ABSOLUTE_URL_RE.match(candidate):
        return candidate
    if candidate.startswith("//"):
        scheme = urlparse(base_url).scheme or "https"
        return f"{scheme}:{candidate}"
    if BARE_HOST_RE.match(candidate):
        return f"https://{candidate}"
    if base_url:
        return urljoin(base_url, candidate)
    return candidate


def _domain_matches(url: str, domains: list[str]) -> bool:
    if not url or not domains:
        return False
    normalized = _normalize_url(url)
    parsed = urlparse(normalized)
    host = (parsed.netloc or parsed.path).lower()
    if "/" in host and not parsed.netloc:
        host = host.split("/", 1)[0]
    if not host:
        return False
    for domain in domains:
        candidate = domain.strip().lower()
        if not candidate:
            continue
        if host == candidate or host.endswith(f".{candidate}") or candidate in host:
            return True
    return False


def _matches_text_allowlist(value: str, allowlist: list[str]) -> bool:
    normalized_value = _normalize_token(value)
    if not normalized_value:
        return False
    return any(
        candidate in normalized_value or normalized_value in candidate
        for candidate in (_normalize_token(item) for item in allowlist)
        if candidate
    )


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


def _extract_publisher(entry: ET.Element, base_url: str) -> tuple[str, str]:
    source_node = entry.find("source")
    if source_node is not None:
        publisher = _strip_html(source_node.text or "")
        publisher_url = _normalize_url(source_node.attrib.get("url", ""), base_url)
        if publisher or publisher_url:
            return publisher, publisher_url

    atom_source = entry.find(f"{ATOM_NS}source")
    if atom_source is not None:
        publisher = _strip_html(
            atom_source.findtext(f"{ATOM_NS}title")
            or atom_source.text
            or ""
        )
        publisher_url = ""
        for atom_link in atom_source.findall(f"{ATOM_NS}link"):
            href = _normalize_url(atom_link.attrib.get("href", ""), base_url)
            if href:
                publisher_url = href
                break
        if publisher or publisher_url:
            return publisher, publisher_url

    return "", ""


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
    fallback_link = (atom_links[0].attrib.get("href") or "").strip()
    if fallback_link:
        return fallback_link

    guid = (entry.findtext("guid") or "").strip()
    return guid if ABSOLUTE_URL_RE.match(guid) else ""


def _matches_filters(
    definition_metadata: dict[str, object],
    *,
    title: str,
    summary: str,
    link: str,
    author: str,
    publisher: str,
    summary_links: list[str],
) -> bool:
    author_allowlist = _coerce_list(definition_metadata.get("author_allowlist"))
    publisher_allowlist = _coerce_list(definition_metadata.get("publisher_allowlist"))
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

    if author_allowlist and not _matches_text_allowlist(author, author_allowlist):
        return False
    if publisher_allowlist and not _matches_text_allowlist(
        publisher,
        publisher_allowlist,
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
    def _timeout_seconds(self) -> float:
        return max(
            1.0,
            _coerce_float(
                self.definition.metadata.get("timeout_seconds"),
                DEFAULT_TIMEOUT_SECONDS,
            ),
        )

    def _retry_attempts(self) -> int:
        return _coerce_int(
            self.definition.metadata.get("retry_attempts"),
            DEFAULT_RETRY_ATTEMPTS,
        )

    def _retry_backoff_seconds(self) -> float:
        return max(
            0.0,
            _coerce_float(
                self.definition.metadata.get("retry_backoff_seconds"),
                DEFAULT_RETRY_BACKOFF_SECONDS,
            ),
        )

    def _request_headers(self) -> dict[str, str]:
        headers = dict(DEFAULT_REQUEST_HEADERS)
        request_headers = self.definition.metadata.get("request_headers")
        if isinstance(request_headers, dict):
            headers.update(
                {
                    compact_whitespace(str(key)): compact_whitespace(str(value))
                    for key, value in request_headers.items()
                    if compact_whitespace(str(key)) and compact_whitespace(str(value))
                }
            )
        user_agent = compact_whitespace(str(self.definition.metadata.get("user_agent", "")))
        if user_agent:
            headers["User-Agent"] = user_agent
        return headers

    def _ssl_context(self) -> ssl.SSLContext:
        if _coerce_bool(self.definition.metadata.get("insecure_ssl")) or _coerce_bool(
            os.environ.get("FITECH_AGENT_INSECURE_SSL")
        ):
            return ssl._create_unverified_context()
        ca_bundle = compact_whitespace(
            str(
                self.definition.metadata.get("ca_bundle_path")
                or os.environ.get("FITECH_AGENT_CA_BUNDLE", "")
            )
        )
        return ssl.create_default_context(cafile=ca_bundle or None)

    def _endpoints(self) -> list[str]:
        candidates = [self.definition.endpoint]
        candidates.extend(_coerce_list(self.definition.metadata.get("fallback_endpoints")))
        seen: set[str] = set()
        endpoints: list[str] = []
        for candidate in candidates:
            normalized = compact_whitespace(candidate)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            endpoints.append(normalized)
        return endpoints

    def _fetch_feed(self) -> tuple[bytes, str]:
        ssl_context = self._ssl_context()
        headers = self._request_headers()
        timeout_seconds = self._timeout_seconds()
        retry_attempts = self._retry_attempts()
        retry_backoff_seconds = self._retry_backoff_seconds()
        errors: list[str] = []

        for endpoint in self._endpoints():
            request = urllib.request.Request(endpoint, headers=headers)
            for attempt in range(1, retry_attempts + 1):
                try:
                    with urllib.request.urlopen(
                        request,
                        timeout=timeout_seconds,
                        context=ssl_context,
                    ) as response:
                        return response.read(), endpoint
                except Exception as exc:
                    errors.append(f"{endpoint} [attempt {attempt}/{retry_attempts}]: {exc}")
                    if attempt < retry_attempts and retry_backoff_seconds > 0:
                        time.sleep(retry_backoff_seconds * attempt)

        if errors:
            raise RuntimeError("; ".join(errors[-3:]))
        raise RuntimeError("feed_fetch_failed")

    def _link_base_url(self, fetched_endpoint: str) -> str:
        configured = compact_whitespace(
            str(self.definition.metadata.get("link_base_url", ""))
        )
        return configured or fetched_endpoint

    def fetch(self, window: NewsWindow, collected_at: str) -> list[RawNewsItem]:
        payload, fetched_endpoint = self._fetch_feed()
        root = ET.fromstring(payload)
        items = []
        window_start = parse_iso_datetime(window.start)
        window_end = parse_iso_datetime(window.end)
        link_base_url = self._link_base_url(fetched_endpoint)
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

            link = _normalize_url(_extract_link(entry), link_base_url)
            author = _extract_author(entry)
            publisher, publisher_url = _extract_publisher(entry, link_base_url)
            summary_links = [
                normalized
                for normalized in (
                    _normalize_url(item, link_base_url)
                    for item in _extract_summary_links(raw_summary)
                )
                if normalized
            ]
            if not _matches_filters(
                self.definition.metadata,
                title=title,
                summary=summary,
                link=link,
                author=author,
                publisher=publisher,
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
                            "entry_publisher": publisher,
                            "entry_publisher_url": publisher_url,
                            "summary_links": summary_links,
                            "window_start": window.start,
                            "window_end": window.end,
                            "fetched_endpoint": fetched_endpoint,
                        },
                    ),
                )
            )
        return items

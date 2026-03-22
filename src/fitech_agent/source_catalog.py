from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True, slots=True)
class SourceProfile:
    tier: str
    level: str
    category: str
    representative_orgs: tuple[str, ...]
    characteristics: str
    best_for: str
    trust_score: float
    priority: int

    def metadata(self) -> dict[str, str]:
        return {
            "source_confidence_level": self.level,
            "source_confidence_category": self.category,
            "source_characteristics": self.characteristics,
            "source_best_for": self.best_for,
            "source_trust_score": f"{self.trust_score:.2f}",
            "source_priority": str(self.priority),
            "source_representative_orgs": ", ".join(self.representative_orgs),
        }


SPACE_RE = re.compile(r"[\s\-_/.:()\[\]{}]+")

TIER_PROFILES = {
    "official": SourceProfile(
        tier="official",
        level="L1",
        category="official_regulatory",
        representative_orgs=("Fed", "PBOC", "SHFE", "COMEX", "NBS"),
        characteristics="Absolute trust anchor and first-order market driver.",
        best_for="Data releases, rule changes, position limits, policy confirmation.",
        trust_score=1.00,
        priority=400,
    ),
    "tier1_media": SourceProfile(
        tier="tier1_media",
        level="L2",
        category="global_top_wire",
        representative_orgs=("Bloomberg", "Reuters"),
        characteristics="Highly trusted with strong cross-checking discipline.",
        best_for="Macro policy direction, global shocks, fast breaking news.",
        trust_score=0.88,
        priority=300,
    ),
    "tier2_media": SourceProfile(
        tier="tier2_media",
        level="L3",
        category="professional_financial_media",
        representative_orgs=("Caixin", "CLS", "Wallstreetcn", "WSJ"),
        characteristics="Useful editorial processing with some interpretation bias.",
        best_for="Chinese translation, sector context, fast professional commentary.",
        trust_score=0.72,
        priority=200,
    ),
    "social": SourceProfile(
        tier="social",
        level="L4",
        category="social_community",
        representative_orgs=("X", "Weibo", "Xueqiu", "Reddit"),
        characteristics="Noisy and mixed-quality, but useful for sentiment sensing.",
        best_for="Retail positioning, sentiment shifts, niche opportunity discovery.",
        trust_score=0.38,
        priority=100,
    ),
    "unknown": SourceProfile(
        tier="unknown",
        level="L4",
        category="unclassified",
        representative_orgs=(),
        characteristics="Unclassified source until manually reviewed.",
        best_for="Supplementary context only; never use as the sole evidence anchor.",
        trust_score=0.50,
        priority=50,
    ),
}

SOURCE_ALIASES = {
    "official": (
        "fed",
        "federal reserve",
        "federalreserve",
        "pboc",
        "pbc",
        "peoples bank of china",
        "people's bank of china",
        "\u4e2d\u56fd\u4eba\u6c11\u94f6\u884c",
        "\u592e\u884c",
        "nbs",
        "national bureau of statistics",
        "\u56fd\u5bb6\u7edf\u8ba1\u5c40",
        "shfe",
        "\u4e0a\u6d77\u671f\u8d27\u4ea4\u6613\u6240",
        "\u4e0a\u671f\u6240",
        "comex",
        "cme",
        "cme group",
        "opec",
        "opec+",
    ),
    "tier1_media": (
        "reuters",
        "\u8def\u900f",
        "bloomberg",
        "\u5f6d\u535a",
    ),
    "tier2_media": (
        "caixin",
        "\u8d22\u65b0",
        "cls",
        "\u8d22\u8054\u793e",
        "wallstreetcn",
        "\u534e\u5c14\u8857\u89c1\u95fb",
        "wsj",
        "wall street journal",
        "\u534e\u5c14\u8857\u65e5\u62a5",
    ),
    "social": (
        "x",
        "twitter",
        "x twitter",
        "x.com",
        "weibo",
        "\u5fae\u535a",
        "xueqiu",
        "\u96ea\u7403",
        "reddit",
    ),
}

NORMALIZED_ALIAS_LOOKUP = {
    SPACE_RE.sub(" ", alias.strip().lower()).strip(): tier
    for tier, aliases in SOURCE_ALIASES.items()
    for alias in aliases
}

DOMAIN_HINTS = {
    "federalreserve.gov": "official",
    "pbc.gov.cn": "official",
    "stats.gov.cn": "official",
    "shfe.com.cn": "official",
    "cmegroup.com": "official",
    "opec.org": "official",
    "reuters.com": "tier1_media",
    "bloomberg.com": "tier1_media",
    "caixin.com": "tier2_media",
    "wallstreetcn.com": "tier2_media",
    "cls.cn": "tier2_media",
    "wsj.com": "tier2_media",
    "x.com": "social",
    "twitter.com": "social",
    "weibo.com": "social",
    "xueqiu.com": "social",
    "reddit.com": "social",
}

TAG_HINTS = {
    "official": "official",
    "regulator": "official",
    "regulatory": "official",
    "exchange": "official",
    "wire": "tier1_media",
    "newswire": "tier1_media",
    "media": "tier2_media",
    "financial_media": "tier2_media",
    "social": "social",
    "community": "social",
    "forum": "social",
}


def normalize_source_name(name: str) -> str:
    return SPACE_RE.sub(" ", (name or "").strip().lower()).strip()


def _infer_from_name(name: str) -> str | None:
    normalized = normalize_source_name(name)
    if not normalized:
        return None
    exact = NORMALIZED_ALIAS_LOOKUP.get(normalized)
    if exact is not None:
        return exact
    for alias, tier in NORMALIZED_ALIAS_LOOKUP.items():
        if alias and alias in normalized:
            return tier
    return None


def _infer_from_endpoint(endpoint: str) -> str | None:
    raw_endpoint = (endpoint or "").strip()
    if not raw_endpoint:
        return None
    parsed = urlparse(raw_endpoint if "://" in raw_endpoint else f"https://{raw_endpoint}")
    host = parsed.netloc.lower() or parsed.path.lower()
    for domain, tier in DOMAIN_HINTS.items():
        if domain in host:
            return tier
    return None


def _infer_from_tags(tags: list[str] | None) -> str | None:
    for tag in tags or []:
        normalized = normalize_source_name(tag)
        tier = TAG_HINTS.get(normalized)
        if tier is not None:
            return tier
    return None


def infer_source_tier(
    name: str,
    explicit_tier: str | None = None,
    *,
    endpoint: str = "",
    tags: list[str] | None = None,
) -> str:
    if explicit_tier and explicit_tier != "unknown":
        return explicit_tier
    for inferred in (
        _infer_from_name(name),
        _infer_from_endpoint(endpoint),
        _infer_from_tags(tags),
    ):
        if inferred is not None:
            return inferred
    return "unknown"


def resolve_source_profile(
    name: str,
    explicit_tier: str | None = None,
    *,
    endpoint: str = "",
    tags: list[str] | None = None,
) -> SourceProfile:
    tier = infer_source_tier(name, explicit_tier, endpoint=endpoint, tags=tags)
    return TIER_PROFILES.get(tier, TIER_PROFILES["unknown"])

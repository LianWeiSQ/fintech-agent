from __future__ import annotations

SOURCE_TIER_BY_NAME = {
    "reuters": "tier1_media",
    "bloomberg": "tier1_media",
    "财联社": "tier2_media",
    "华尔街见闻": "tier2_media",
    "中国人民银行": "official",
    "国家统计局": "official",
    "国家能源局": "official",
    "opec": "official",
    "fed": "official",
    "federal reserve": "official",
    "cme": "official",
    "cme group": "official",
    "pboc": "official",
}


def normalize_source_name(name: str) -> str:
    return " ".join((name or "").strip().lower().split())


def infer_source_tier(name: str, explicit_tier: str | None = None) -> str:
    if explicit_tier:
        return explicit_tier
    return SOURCE_TIER_BY_NAME.get(normalize_source_name(name), "unknown")

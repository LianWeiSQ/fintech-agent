from __future__ import annotations

import re
from collections import defaultdict

from ....models import NewsCluster, RawNewsItem
from ....utils import compact_whitespace, iso_day, stable_id

LEXICON = {
    r"美联储|联储|联邦公开市场委员会": "federal reserve ",
    r"fomc": "federal reserve ",
    r"中国人民银行|央行": "pboc ",
    r"美国消费者价格指数|cpi": "cpi ",
    r"非农就业|nonfarm payrolls?": "nonfarm payrolls ",
    r"石油输出国组织|欧佩克|opec\+": "opec ",
    r"刺激政策|稳增长": "china stimulus ",
    r"关税": "tariff ",
    r"停火|地缘冲突|空袭|袭击": "geopolitics ",
    r"降息": "rate cut ",
    r"加息": "rate hike ",
    r"鹰派": "hawkish ",
    r"鸽派": "dovish ",
}

STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "into",
    "amid",
    "after",
    "china",
    "market",
    "macro",
    "news",
}

EVENT_KEYS = {
    "fomc": ["federal reserve", "rates", "rate hike", "rate cut"],
    "us_cpi": ["cpi"],
    "us_nonfarm": ["nonfarm payrolls"],
    "china_policy": ["pboc", "china stimulus", "policy", "fiscal", "growth"],
    "opec": ["opec", "supply cut", "production"],
    "geopolitics": ["geopolitics", "conflict", "attack", "tariff"],
    "energy_supply": ["oil", "pipeline", "output", "supply"],
}


def normalize_text(text: str) -> str:
    normalized = compact_whitespace((text or "").lower())
    for pattern, replacement in LEXICON.items():
        normalized = re.sub(pattern, replacement, normalized)
    normalized = re.sub(r"[^0-9a-z\u4e00-\u9fff\s]", " ", normalized)
    return compact_whitespace(normalized)


def derive_cluster_key(item: RawNewsItem, normalized_text: str) -> str:
    day = iso_day(item.published_at) or iso_day(item.collected_at)
    for event_key, hints in EVENT_KEYS.items():
        matches = sum(1 for hint in hints if hint in normalized_text)
        if matches >= 1:
            return f"{day}:{event_key}"
    tokens = [
        token
        for token in re.findall(r"[a-z0-9_]{3,}", normalized_text)
        if token not in STOPWORDS
    ]
    fingerprint = "_".join(tokens[:6]) or stable_id(item.title, day, size=10)
    return f"{day}:{fingerprint}"


class NormalizationAgent:
    def run(self, items: list[RawNewsItem]) -> list[NewsCluster]:
        grouped: dict[str, list[RawNewsItem]] = defaultdict(list)
        normalized_lookup: dict[str, str] = {}

        for item in items:
            normalized = normalize_text(f"{item.title} {item.summary}")
            cluster_key = derive_cluster_key(item, normalized)
            grouped[cluster_key].append(item)
            normalized_lookup[cluster_key] = normalized

        clusters: list[NewsCluster] = []
        for cluster_key, grouped_items in grouped.items():
            ordered = sorted(grouped_items, key=lambda entry: entry.published_at)
            languages = sorted({entry.language for entry in ordered})
            clusters.append(
                NewsCluster(
                    id=stable_id(cluster_key, size=16),
                    cluster_key=cluster_key,
                    normalized_text=normalized_lookup[cluster_key],
                    first_seen_at=ordered[0].published_at,
                    source_languages=languages,
                    items=ordered,
                )
            )
        return sorted(clusters, key=lambda cluster: cluster.first_seen_at, reverse=True)

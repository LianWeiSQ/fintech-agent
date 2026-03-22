from __future__ import annotations

from collections import Counter

from ....llm import LiteLLMClient
from ....models import CanonicalNewsEvent, EvidenceRef, NewsCluster, RawNewsItem
from ....utils import compact_whitespace, stable_id
from .. import prompts
from ..runtime import EventIntelligenceRuntime
from .translate_or_summarize import needs_translation


def _tier_rank(tier: str) -> int:
    return {
        "official": 0,
        "tier1_media": 1,
        "tier2_media": 2,
        "social": 3,
        "unknown": 4,
    }.get(tier, 5)


def _trust_score(item: RawNewsItem) -> float:
    raw_score = item.metadata.get("source_trust_score", 0.0)
    try:
        return float(raw_score)
    except (TypeError, ValueError):
        return 0.0


def _source_mix_metadata(items: list[RawNewsItem]) -> dict[str, object]:
    tier_counts = Counter(item.source_tier for item in items)
    level_counts = Counter(
        str(item.metadata.get("source_confidence_level", "unknown"))
        for item in items
    )
    trust_scores = [_trust_score(item) for item in items]
    average_trust = sum(trust_scores) / len(trust_scores) if trust_scores else 0.0
    return {
        "source_count": len(items),
        "source_tier_counts": dict(tier_counts),
        "source_level_counts": dict(level_counts),
        "source_names": list(dict.fromkeys(item.source for item in items)),
        "avg_source_trust": round(average_trust, 2),
        "max_source_trust": round(max(trust_scores), 2) if trust_scores else 0.0,
        "has_l1_anchor": level_counts.get("L1", 0) > 0,
        "has_l2_anchor": level_counts.get("L2", 0) > 0,
    }


def detect_event_type(normalized_text: str) -> str:
    if "federal reserve" in normalized_text:
        return "fomc"
    if "cpi" in normalized_text:
        return "us_cpi"
    if "nonfarm payrolls" in normalized_text:
        return "us_nonfarm"
    if "opec" in normalized_text:
        return "opec"
    if "pboc" in normalized_text or "china stimulus" in normalized_text:
        return "china_policy"
    if "geopolitics" in normalized_text or "tariff" in normalized_text:
        return "geopolitics"
    if "oil" in normalized_text or "supply" in normalized_text:
        return "energy_supply"
    return "macro_growth"


def detect_bias(normalized_text: str, event_type: str) -> str:
    if "hawkish" in normalized_text or "rate hike" in normalized_text:
        return "hawkish"
    if "dovish" in normalized_text or "rate cut" in normalized_text:
        return "dovish"
    if "china stimulus" in normalized_text or "support" in normalized_text:
        return "supportive"
    if "tariff" in normalized_text or "geopolitics" in normalized_text:
        return "risk_off"
    if event_type in {"opec", "energy_supply"} and (
        "cut" in normalized_text or "attack" in normalized_text
    ):
        return "supply_tightening"
    return "neutral"


def detect_regions(event_type: str) -> list[str]:
    if event_type in {"fomc", "us_cpi", "us_nonfarm"}:
        return ["US", "Global"]
    if event_type == "china_policy":
        return ["China", "Asia"]
    if event_type in {"opec", "energy_supply", "geopolitics"}:
        return ["Global", "Middle East"]
    return ["Global"]


class EventExtractionAgent:
    def __init__(
        self,
        llm_client: LiteLLMClient,
        report_language: str,
        runtime: EventIntelligenceRuntime | None = None,
    ) -> None:
        self.llm_client = llm_client
        self.report_language = report_language
        self.runtime = runtime

    def _translate(self, text: str) -> str:
        if self.runtime is None:
            return self.llm_client.translate(text, target_language=self.report_language)
        return self.llm_client.translate(
            text,
            target_language=self.report_language,
            system_prompt=self.runtime.system_prompt(prompts.TRANSLATION_INSTRUCTION),
        )

    def run(self, clusters: list[NewsCluster]) -> list[CanonicalNewsEvent]:
        events: list[CanonicalNewsEvent] = []
        for cluster in clusters:
            ranked = sorted(
                cluster.items,
                key=lambda item: (_tier_rank(item.source_tier), -_trust_score(item), item.published_at),
            )
            primary = ranked[0]
            event_type = detect_event_type(cluster.normalized_text)
            bias = detect_bias(cluster.normalized_text, event_type)
            summary_seed = primary.summary or primary.title
            if needs_translation(self.report_language, primary.language):
                summary_seed = self._translate(summary_seed)
            titles = list(dict.fromkeys(item.title for item in ranked if item.title))
            evidence = [
                EvidenceRef(
                    source=item.source,
                    source_tier=item.source_tier,
                    title=item.title,
                    url=item.url,
                    published_at=item.published_at,
                    language=item.language,
                )
                for item in ranked[:6]
            ]
            preferred_language = "zh" if "zh" in cluster.source_languages else primary.language
            title = primary.title
            if preferred_language == "zh":
                zh_titles = [item.title for item in ranked if item.language.startswith("zh")]
                if zh_titles:
                    title = zh_titles[0]
            metadata = _source_mix_metadata(ranked)
            metadata.update(
                {
                    "primary_source": primary.source,
                    "primary_source_tier": primary.source_tier,
                    "primary_source_level": primary.metadata.get("source_confidence_level", "unknown"),
                }
            )
            events.append(
                CanonicalNewsEvent(
                    id=stable_id(cluster.id, event_type, bias, size=16),
                    cluster_id=cluster.id,
                    event_type=event_type,
                    bias=bias,
                    title=compact_whitespace(title),
                    summary=compact_whitespace(summary_seed),
                    normalized_text=cluster.normalized_text,
                    primary_language=preferred_language,
                    source_languages=cluster.source_languages,
                    published_at=primary.published_at,
                    regions=detect_regions(event_type),
                    tags=[event_type, bias],
                    supporting_titles=titles[:5],
                    evidence_refs=evidence,
                    metadata=metadata,
                )
            )
        return events

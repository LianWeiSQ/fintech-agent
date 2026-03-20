from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

Direction = Literal["bullish", "bearish", "neutral", "watch"]
SourceTier = Literal["official", "tier1_media", "tier2_media", "social", "unknown"]


@dataclass(slots=True)
class Serializable:
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class NewsWindow(Serializable):
    start: str
    end: str


@dataclass(slots=True)
class RawNewsItem(Serializable):
    id: str
    source: str
    source_type: str
    source_tier: SourceTier
    language: str
    title: str
    summary: str
    url: str
    published_at: str
    collected_at: str
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RawNewsItem":
        return cls(**payload)


@dataclass(slots=True)
class EvidenceRef(Serializable):
    source: str
    source_tier: SourceTier
    title: str
    url: str
    published_at: str
    language: str

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "EvidenceRef":
        return cls(**payload)


@dataclass(slots=True)
class NewsCluster(Serializable):
    id: str
    cluster_key: str
    normalized_text: str
    first_seen_at: str
    source_languages: list[str]
    items: list[RawNewsItem]


@dataclass(slots=True)
class CanonicalNewsEvent(Serializable):
    id: str
    cluster_id: str
    event_type: str
    bias: str
    title: str
    summary: str
    normalized_text: str
    primary_language: str
    source_languages: list[str]
    published_at: str
    regions: list[str]
    tags: list[str]
    supporting_titles: list[str]
    evidence_refs: list[EvidenceRef]
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "CanonicalNewsEvent":
        payload = dict(payload)
        payload["evidence_refs"] = [
            EvidenceRef.from_dict(item) for item in payload.get("evidence_refs", [])
        ]
        return cls(**payload)


@dataclass(slots=True)
class CredibilityScore(Serializable):
    event_id: str
    score: float
    verified: bool
    tier: str
    rationale: list[str]
    blocking_issues: list[str]

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "CredibilityScore":
        return cls(**payload)


@dataclass(slots=True)
class EventAssetMap(Serializable):
    event_id: str
    assets: list[str]
    sectors: list[str]
    macro_factors: list[str]
    rationale: list[str]

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "EventAssetMap":
        return cls(**payload)


@dataclass(slots=True)
class MarketImpactAssessment(Serializable):
    id: str
    event_id: str
    domain: str
    impacted_assets: list[str]
    impacted_sectors: list[str]
    direction: Direction
    confidence: float
    horizon: str
    transmission_path: list[str]
    key_evidence: list[EvidenceRef]
    counter_evidence: list[str]
    watchlist: list[str]
    strategy_view: str
    downside_risks: list[str]
    status: str
    credibility_score: float

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "MarketImpactAssessment":
        payload = dict(payload)
        payload["key_evidence"] = [
            EvidenceRef.from_dict(item) for item in payload.get("key_evidence", [])
        ]
        return cls(**payload)


@dataclass(slots=True)
class IntegratedView(Serializable):
    cross_asset_themes: list[str]
    equity_view: list[str]
    commodities_view: list[str]
    precious_metals_view: list[str]
    crude_oil_view: list[str]
    risk_scenarios: list[str]
    watchlist: list[str]


@dataclass(slots=True)
class DailyMarketBrief(Serializable):
    report_id: str
    run_id: int
    scheduled_for: str
    generated_at: str
    overnight_focus: list[str]
    core_events: list[str]
    cross_asset_themes: list[str]
    equity_view: list[str]
    commodities_view: list[str]
    precious_metals_view: list[str]
    crude_oil_view: list[str]
    risk_scenarios: list[str]
    watchlist: list[str]
    evidence_appendix: list[str]
    markdown_body: str
    degraded: bool
    degraded_reasons: list[str]

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DailyMarketBrief":
        return cls(**payload)


@dataclass(slots=True)
class ForecastOutcome(Serializable):
    run_id: int
    assessment_id: str
    asset: str
    evaluation_window: str
    observed_direction: str
    observed_move: float
    hit: bool
    notes: str


@dataclass(slots=True)
class PriceObservation(Serializable):
    asset: str
    evaluation_window: str
    observed_direction: str
    observed_move: float
    notes: str = ""


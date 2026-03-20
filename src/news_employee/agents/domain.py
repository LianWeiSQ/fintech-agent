from __future__ import annotations

from collections import defaultdict

from ..models import CanonicalNewsEvent, CredibilityScore, EventAssetMap, MarketImpactAssessment
from ..utils import stable_id


def _group_assets_by_domain(assets: list[str]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for asset in assets:
        if asset.startswith("cn_equities"):
            grouped["equities"].append(asset)
        elif asset.startswith("precious_metals"):
            grouped["precious_metals"].append(asset)
        elif asset.startswith("energy"):
            grouped["energy"].append(asset)
        elif asset.startswith("cn_futures"):
            grouped["commodities"].append(asset)
        else:
            grouped["macro"].append(asset)
    return dict(grouped)


def _direction_for_domain(event_type: str, bias: str, domain: str) -> str:
    if domain == "macro":
        if bias == "hawkish":
            return "bullish"
        if bias == "dovish":
            return "bearish"
        return "neutral"
    if domain == "equities":
        if bias in {"hawkish", "risk_off"}:
            return "bearish"
        if bias in {"dovish", "supportive"}:
            return "bullish"
        return "neutral"
    if domain == "precious_metals":
        if bias == "hawkish":
            return "bearish"
        if bias in {"dovish", "risk_off"}:
            return "bullish"
        return "neutral"
    if domain == "energy":
        if event_type in {"opec", "energy_supply", "geopolitics"} and bias in {"supply_tightening", "risk_off"}:
            return "bullish"
        return "neutral"
    if domain == "commodities":
        if bias == "supportive":
            return "bullish"
        if bias == "risk_off":
            return "bearish"
        return "neutral"
    return "neutral"


def _horizon_for_event(event_type: str) -> str:
    if event_type in {"fomc", "us_cpi", "us_nonfarm"}:
        return "D0-D5"
    if event_type == "china_policy":
        return "D1-D10"
    if event_type in {"opec", "energy_supply", "geopolitics"}:
        return "D0-D10"
    return "D0-D3"


def _transmission_path(event_type: str, bias: str, domain: str) -> list[str]:
    paths = {
        ("fomc", "equities"): ["Fed rhetoric", "US rates", "risk appetite", "A-share valuation"],
        ("fomc", "precious_metals"): ["Fed rhetoric", "real yields", "USD", "gold/silver"],
        ("china_policy", "equities"): ["Policy support", "growth expectations", "cyclicals"],
        ("china_policy", "commodities"): ["Policy support", "domestic demand", "industrial futures"],
        ("opec", "energy"): ["OPEC supply", "crude balances", "oil prices"],
        ("geopolitics", "energy"): ["Conflict premium", "supply risk", "crude prices"],
        ("geopolitics", "precious_metals"): ["Risk-off flow", "safe havens", "gold/silver"],
    }
    return paths.get((event_type, domain), [event_type, bias, domain])


def _strategy_view(domain: str, direction: str, event: CanonicalNewsEvent) -> str:
    prefix = {"bullish": "偏多", "bearish": "偏空", "neutral": "中性", "watch": "观察"}[direction]
    if domain == "equities":
        return f"{prefix}A股与重点板块，核心驱动来自“{event.title}”对风险偏好和盈利预期的重估。"
    if domain == "precious_metals":
        return f"{prefix}黄金白银，重点观察“{event.title}”对美元与实际利率链条的影响。"
    if domain == "energy":
        return f"{prefix}原油与能源链，核心变量是“{event.title}”带来的供给风险溢价。"
    if domain == "commodities":
        return f"{prefix}国内商品期货，关注“{event.title}”对需求和风险偏好的传导。"
    return f"{prefix}美元/利率主线，关注“{event.title}”对宏观定价中枢的影响。"


def _downside_risks(event_type: str, bias: str) -> list[str]:
    if bias == "hawkish":
        return ["若后续通胀快速回落，鹰派交易可能回吐。"]
    if bias == "dovish":
        return ["若通胀二次上行，宽松预期会被修正。"]
    if bias == "supportive":
        return ["若政策落地弱于预期，顺周期交易可能失速。"]
    if bias in {"risk_off", "supply_tightening"}:
        return ["若地缘或供给扰动迅速缓和，风险溢价会明显收缩。"]
    return ["若后续验证不足，需要下调事件权重。"]


def _watchlist(event_type: str) -> list[str]:
    mapping = {
        "fomc": ["联储官员后续讲话", "美债收益率", "美元指数"],
        "us_cpi": ["核心通胀分项", "市场降息预期"],
        "us_nonfarm": ["失业率与薪资增速", "降息预期"],
        "china_policy": ["政策细则", "地产与信用数据", "北向资金"],
        "opec": ["OPEC执行率", "EIA库存", "航运数据"],
        "geopolitics": ["冲突升级节奏", "航道与制裁变化"],
    }
    return mapping.get(event_type, ["后续权威验证", "价格确认"])


class DomainAnalysisAgent:
    def run(self, events: list[CanonicalNewsEvent], credibility_scores: list[CredibilityScore], mappings: list[EventAssetMap]) -> list[MarketImpactAssessment]:
        score_lookup = {score.event_id: score for score in credibility_scores}
        mapping_lookup = {mapping.event_id: mapping for mapping in mappings}
        assessments: list[MarketImpactAssessment] = []

        for event in events:
            mapping = mapping_lookup.get(event.id)
            if mapping is None:
                continue
            grouped_assets = _group_assets_by_domain(mapping.assets)
            score = score_lookup.get(event.id)
            credibility_score = score.score if score else 0.0
            evidence = event.evidence_refs[:3]
            for domain, impacted_assets in grouped_assets.items():
                direction = _direction_for_domain(event.event_type, event.bias, domain)
                confidence = round(min(0.95, 0.35 + credibility_score * 0.55), 2)
                assessments.append(
                    MarketImpactAssessment(
                        id=stable_id(event.id, domain, direction, size=16),
                        event_id=event.id,
                        domain=domain,
                        impacted_assets=impacted_assets,
                        impacted_sectors=list(mapping.sectors),
                        direction=direction,
                        confidence=confidence,
                        horizon=_horizon_for_event(event.event_type),
                        transmission_path=_transmission_path(event.event_type, event.bias, domain),
                        key_evidence=evidence,
                        counter_evidence=[risk for risk in _downside_risks(event.event_type, event.bias)],
                        watchlist=_watchlist(event.event_type),
                        strategy_view=_strategy_view(domain, direction, event),
                        downside_risks=_downside_risks(event.event_type, event.bias),
                        status="draft",
                        credibility_score=credibility_score,
                    )
                )
        return assessments

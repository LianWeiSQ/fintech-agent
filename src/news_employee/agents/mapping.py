from __future__ import annotations

from ..models import CanonicalNewsEvent, EventAssetMap


def _mapping_for_event(event: CanonicalNewsEvent) -> tuple[list[str], list[str], list[str], list[str]]:
    event_type = event.event_type
    bias = event.bias
    assets: list[str] = []
    sectors: list[str] = []
    macro_factors: list[str] = []
    rationale: list[str] = []

    if event_type in {"fomc", "us_cpi", "us_nonfarm"}:
        assets.extend([
            "macro/usd",
            "macro/us_rates",
            "precious_metals/gold",
            "precious_metals/silver",
            "cn_equities/major_indices",
        ])
        sectors.extend(["cn_equities/growth", "cn_equities/financials"])
        macro_factors.extend(["usd_liquidity", "global_yields", "risk_appetite"])
        rationale.append("US macro and Fed-sensitive events reset dollar, rates, and risk appetite.")
    if event_type == "china_policy":
        assets.extend(["cn_equities/major_indices", "cn_futures/industrial", "macro/cny"])
        sectors.extend(["cn_equities/cyclicals", "cn_equities/brokers", "cn_equities/real_estate"])
        macro_factors.extend(["china_growth", "policy_support"])
        rationale.append("China policy signals drive domestic growth expectations and cyclicals.")
    if event_type in {"opec", "energy_supply"}:
        assets.extend(["energy/crude_oil", "cn_futures/energy"])
        sectors.extend(["cn_equities/energy", "cn_equities/transport"])
        macro_factors.extend(["oil_supply", "inflation_expectations"])
        rationale.append("Supply-side energy events reprice crude and inflation-sensitive assets.")
    if event_type == "geopolitics":
        assets.extend(["energy/crude_oil", "precious_metals/gold", "precious_metals/silver"])
        sectors.extend(["cn_equities/defensives", "cn_equities/energy"])
        macro_factors.extend(["risk_appetite", "safe_haven_flow"])
        rationale.append("Geopolitical shocks typically benefit safe havens and raise oil risk premium.")

    if bias in {"hawkish", "risk_off"}:
        rationale.append("Current bias is tightening / risk-off.")
    elif bias in {"dovish", "supportive"}:
        rationale.append("Current bias is easing / policy support.")
    elif bias == "supply_tightening":
        rationale.append("The event points to tighter commodity supply.")

    unique_assets = list(dict.fromkeys(assets))
    unique_sectors = list(dict.fromkeys(sectors))
    unique_factors = list(dict.fromkeys(macro_factors))
    return unique_assets, unique_sectors, unique_factors, rationale


class AssetMappingAgent:
    def run(self, events: list[CanonicalNewsEvent]) -> list[EventAssetMap]:
        mappings: list[EventAssetMap] = []
        for event in events:
            assets, sectors, macro_factors, rationale = _mapping_for_event(event)
            mappings.append(
                EventAssetMap(
                    event_id=event.id,
                    assets=assets,
                    sectors=sectors,
                    macro_factors=macro_factors,
                    rationale=rationale or ["Mapped through default macro linkage."],
                )
            )
        return mappings

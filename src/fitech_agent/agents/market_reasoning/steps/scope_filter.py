from __future__ import annotations

from ....models import ALL_RESEARCH_SCOPES, CanonicalNewsEvent, EventAssetMap

DIRECT_ASSET_SCOPES = {
    "equity",
    "commodities",
    "precious_metals",
    "crude_oil",
    "usd",
    "ust",
}

THEMATIC_SCOPES = {
    "risk_sentiment",
    "cn_policy",
    "global_macro",
}


def mapping_scopes(event: CanonicalNewsEvent, mapping: EventAssetMap) -> set[str]:
    scopes: set[str] = set()
    for asset in mapping.assets:
        if asset.startswith("cn_equities/"):
            scopes.add("equity")
        if asset.startswith("cn_futures/"):
            scopes.add("commodities")
        if asset.startswith("precious_metals/"):
            scopes.add("precious_metals")
        if asset.startswith("energy/"):
            scopes.add("crude_oil")
        if asset == "macro/usd":
            scopes.add("usd")
        if asset == "macro/us_rates":
            scopes.add("ust")
        if asset == "macro/cny":
            scopes.add("cn_policy")
    for factor in mapping.macro_factors:
        if factor in {"risk_appetite", "safe_haven_flow"}:
            scopes.add("risk_sentiment")
        if factor in {"policy_support", "china_growth"}:
            scopes.add("cn_policy")
        if factor in {"usd_liquidity", "global_yields", "inflation_expectations", "oil_supply"}:
            scopes.add("global_macro")
    if event.event_type == "china_policy":
        scopes.add("cn_policy")
    if event.event_type in {
        "fomc",
        "us_cpi",
        "us_nonfarm",
        "opec",
        "energy_supply",
        "geopolitics",
        "macro_growth",
    }:
        scopes.add("global_macro")
    return scopes


def asset_scopes(asset: str) -> set[str]:
    scopes: set[str] = set()
    if asset.startswith("cn_equities/"):
        scopes.add("equity")
    if asset.startswith("cn_futures/"):
        scopes.add("commodities")
    if asset.startswith("precious_metals/"):
        scopes.add("precious_metals")
    if asset.startswith("energy/"):
        scopes.add("crude_oil")
    if asset == "macro/usd":
        scopes.add("usd")
    if asset == "macro/us_rates":
        scopes.add("ust")
    if asset == "macro/cny":
        scopes.add("cn_policy")
    return scopes


def sector_scopes(sector: str) -> set[str]:
    if sector.startswith("cn_equities/"):
        return {"equity"}
    return set()


def filter_by_scope(
    events: list[CanonicalNewsEvent],
    mappings: list[EventAssetMap],
    selected_scopes: list[str],
) -> tuple[list[CanonicalNewsEvent], list[EventAssetMap]]:
    if set(selected_scopes) == set(ALL_RESEARCH_SCOPES):
        return list(events), list(mappings)

    selected = set(selected_scopes)
    mapping_lookup = {mapping.event_id: mapping for mapping in mappings}
    filtered_events: list[CanonicalNewsEvent] = []
    filtered_mappings: list[EventAssetMap] = []

    for event in events:
        mapping = mapping_lookup.get(event.id)
        if mapping is None:
            continue
        event_scope_set = mapping_scopes(event, mapping)
        if not (event_scope_set & selected):
            continue

        thematic_match = bool(event_scope_set & selected & THEMATIC_SCOPES)
        if thematic_match:
            filtered_events.append(event)
            filtered_mappings.append(mapping)
            continue

        filtered_assets = [
            asset
            for asset in mapping.assets
            if asset_scopes(asset) & selected & DIRECT_ASSET_SCOPES
        ]
        if not filtered_assets:
            continue

        filtered_events.append(event)
        filtered_mappings.append(
            EventAssetMap(
                event_id=mapping.event_id,
                assets=filtered_assets,
                sectors=[
                    sector
                    for sector in mapping.sectors
                    if sector_scopes(sector) & selected
                ],
                macro_factors=list(mapping.macro_factors),
                rationale=list(mapping.rationale),
            )
        )

    return filtered_events, filtered_mappings

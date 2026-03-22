from __future__ import annotations

from collections import Counter

from ....models import CanonicalNewsEvent, CredibilityScore

WEIGHTS = {
    "official": 1.00,
    "tier1_media": 0.88,
    "tier2_media": 0.72,
    "social": 0.38,
    "unknown": 0.50,
}

LEVEL_LABELS = {
    "official": "L1",
    "tier1_media": "L2",
    "tier2_media": "L3",
    "social": "L4",
    "unknown": "L4",
}


class CredibilityAgent:
    def run(self, events: list[CanonicalNewsEvent]) -> list[CredibilityScore]:
        scores: list[CredibilityScore] = []
        for event in events:
            evidence = event.evidence_refs
            counts = Counter(item.source_tier for item in evidence)
            source_names = {item.source for item in evidence if item.source}
            weights = [WEIGHTS.get(item.source_tier, 0.50) for item in evidence]
            average_weight = sum(weights) / len(weights) if weights else 0.0

            official_count = counts.get("official", 0)
            tier1_count = counts.get("tier1_media", 0)
            tier2_count = counts.get("tier2_media", 0)
            social_count = counts.get("social", 0)
            unknown_count = counts.get("unknown", 0)
            distinct_high_signal = sum(
                1
                for value in (official_count, tier1_count, tier2_count)
                if value > 0
            )

            corroboration_bonus = min(0.12, max(0, len(source_names) - 1) * 0.03)
            anchor_bonus = 0.0
            if official_count > 0:
                anchor_bonus = 0.08
            elif tier1_count >= 2:
                anchor_bonus = 0.07
            elif tier1_count >= 1 and tier2_count >= 1:
                anchor_bonus = 0.05
            elif tier2_count >= 2:
                anchor_bonus = 0.03

            diversity_bonus = 0.03 if distinct_high_signal >= 2 else 0.0
            penalty = 0.0
            if len(source_names) <= 1:
                penalty += 0.07
            if official_count == 0 and tier1_count == 0 and tier2_count == 0:
                penalty += 0.15
            elif social_count > 0 and official_count == 0 and tier1_count == 0:
                penalty += 0.08
            if unknown_count > 0 and official_count == 0 and tier1_count == 0:
                penalty += 0.04

            score = round(
                max(0.05, min(0.99, average_weight + corroboration_bonus + anchor_bonus + diversity_bonus - penalty)),
                2,
            )
            verified = (
                official_count > 0
                or tier1_count >= 2
                or (tier1_count >= 1 and tier2_count >= 1 and len(source_names) >= 2)
            )

            blocking_issues: list[str] = []
            if not evidence:
                blocking_issues.append("missing_evidence")
            if len(source_names) <= 1:
                blocking_issues.append("single_source_event")
            if official_count == 0 and tier1_count == 0:
                blocking_issues.append("no_l1_l2_anchor")
            if social_count > 0 and social_count >= max(1, official_count + tier1_count + tier2_count):
                blocking_issues.append("social_dominant_source_mix")
            if not verified:
                blocking_issues.append("unverified_source_mix")

            if score >= 0.82:
                tier = "high"
            elif score >= 0.62:
                tier = "medium"
            else:
                tier = "low"

            rationale = [
                (
                    "source mix "
                    f"L1={official_count}, L2={tier1_count}, L3={tier2_count}, "
                    f"L4={social_count + unknown_count}"
                ),
                f"average source weight {average_weight:.2f}",
            ]
            if official_count > 0:
                rationale.append("official or regulatory source present")
            elif tier1_count >= 2:
                rationale.append("confirmed by multiple top-wire sources")
            elif tier1_count >= 1 and tier2_count >= 1:
                rationale.append("confirmed by wire plus professional financial media")
            else:
                top_level = LEVEL_LABELS.get(next(iter(counts), "unknown"), "L4") if counts else "L4"
                rationale.append(f"best available anchor remains {top_level}")

            scores.append(
                CredibilityScore(
                    event_id=event.id,
                    score=score,
                    verified=verified,
                    tier=tier,
                    rationale=rationale,
                    blocking_issues=blocking_issues,
                )
            )
        return scores

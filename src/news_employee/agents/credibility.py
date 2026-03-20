from __future__ import annotations

from ..models import CanonicalNewsEvent, CredibilityScore

WEIGHTS = {
    "official": 1.0,
    "tier1_media": 0.85,
    "tier2_media": 0.65,
    "social": 0.35,
    "unknown": 0.5,
}


class CredibilityAgent:
    def run(self, events: list[CanonicalNewsEvent]) -> list[CredibilityScore]:
        scores: list[CredibilityScore] = []
        for event in events:
            evidence = event.evidence_refs
            weights = [WEIGHTS.get(item.source_tier, 0.5) for item in evidence]
            average_weight = sum(weights) / len(weights) if weights else 0.0
            corroboration_bonus = min(0.12, max(0, len(evidence) - 1) * 0.04)
            score = round(min(0.99, average_weight + corroboration_bonus), 2)
            verified = any(item.source_tier == "official" for item in evidence) or sum(
                1 for item in evidence if item.source_tier == "tier1_media"
            ) >= 2
            blocking_issues = []
            if not evidence:
                blocking_issues.append("missing_evidence")
            if all(item.source_tier in {"social", "unknown"} for item in evidence):
                blocking_issues.append("unverified_source_mix")
            if len(evidence) == 1:
                blocking_issues.append("single_source_event")
            if score >= 0.8:
                tier = "high"
            elif score >= 0.6:
                tier = "medium"
            else:
                tier = "low"
            scores.append(
                CredibilityScore(
                    event_id=event.id,
                    score=score,
                    verified=verified,
                    tier=tier,
                    rationale=[
                        f"{len(evidence)} supporting source(s)",
                        f"average source weight {average_weight:.2f}",
                    ],
                    blocking_issues=blocking_issues,
                )
            )
        return scores

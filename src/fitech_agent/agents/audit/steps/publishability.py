from __future__ import annotations

from dataclasses import replace

from ....config import AuditSettings
from ....models import CredibilityScore, MarketImpactAssessment


class EvidenceAuditAgent:
    def __init__(self, settings: AuditSettings) -> None:
        self.settings = settings

    def run(self, assessments: list[MarketImpactAssessment], credibility_scores: list[CredibilityScore]) -> tuple[list[MarketImpactAssessment], list[str]]:
        score_lookup = {score.event_id: score for score in credibility_scores}
        audited: list[MarketImpactAssessment] = []
        notes: list[str] = []
        for assessment in assessments:
            score = score_lookup.get(assessment.event_id)
            publishable = (
                score is not None
                and score.verified
                and score.score >= self.settings.min_verified_score
                and assessment.confidence >= self.settings.min_publish_confidence
                and bool(assessment.key_evidence)
            )
            status = "ready" if publishable else "watch_only"
            if not publishable:
                notes.append(
                    "audit_downgrade:"
                    f"{assessment.id}:verified={score.verified if score else False}:"
                    f"score={score.score if score else 0.0}:"
                    f"confidence={assessment.confidence}"
                )
            audited.append(replace(assessment, status=status))
        return audited, notes

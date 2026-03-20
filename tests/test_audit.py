from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fitech_agent.agents.audit import EvidenceAuditAgent
from fitech_agent.config import AuditSettings
from fitech_agent.models import CredibilityScore, EvidenceRef, MarketImpactAssessment


class AuditTests(unittest.TestCase):
    def test_low_credibility_assessment_is_downgraded(self) -> None:
        assessment = MarketImpactAssessment(
            id="impact-1",
            event_id="event-1",
            domain="precious_metals",
            impacted_assets=["precious_metals/gold"],
            impacted_sectors=[],
            direction="bullish",
            confidence=0.72,
            horizon="D0-D5",
            transmission_path=["risk-off", "gold"],
            key_evidence=[
                EvidenceRef(
                    source="social_feed",
                    source_tier="social",
                    title="Rumor headline",
                    url="https://example.com/rumor",
                    published_at="2026-03-19T21:00:00Z",
                    language="en",
                )
            ],
            counter_evidence=[],
            watchlist=[],
            strategy_view="?????",
            downside_risks=[],
            status="draft",
            credibility_score=0.3,
        )
        scores = [
            CredibilityScore(
                event_id="event-1",
                score=0.35,
                verified=False,
                tier="low",
                rationale=["single social source"],
                blocking_issues=["unverified_source_mix"],
            )
        ]
        audited, notes = EvidenceAuditAgent(AuditSettings()).run([assessment], scores)
        self.assertEqual(audited[0].status, "watch_only")
        self.assertTrue(notes)


if __name__ == "__main__":
    unittest.main()

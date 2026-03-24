from __future__ import annotations

import sys
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fitech_agent.agents.audit import EvidenceAuditAgent
from fitech_agent.agents.event_intelligence.steps.credibility import CredibilityAgent
from fitech_agent.config import AuditSettings, SourceDefinition, load_config
from fitech_agent.models import CanonicalNewsEvent, CredibilityScore, EvidenceRef, MarketImpactAssessment


class SourceConfidenceTests(unittest.TestCase):
    def test_load_config_preserves_list_metadata(self) -> None:
        config_text = """
timezone = "Asia/Shanghai"

[run_defaults]
mode = "full_report"
lookback_hours = 18

[[sources]]
name = "ReutersMarketsX"
kind = "rss"
endpoint = "https://rsshub.app/twitter/user/ReutersMarkets"
language = "en"
tier = "tier1_media"
metadata.title_allowlist_keywords = ["fed", "yield"]
metadata.summary_href_allowlist_domains = ["reuters.com"]
"""
        temp_dir = ROOT / "artifacts" / "test_tmp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        config_path = temp_dir / f"config_{uuid.uuid4().hex}.toml"
        config_path.write_text(config_text, encoding="utf-8")
        try:
            config = load_config(config_path)
        finally:
            config_path.unlink(missing_ok=True)

        self.assertEqual(len(config.sources), 1)
        self.assertEqual(
            config.sources[0].metadata["title_allowlist_keywords"],
            ["fed", "yield"],
        )
        self.assertEqual(
            config.sources[0].metadata["summary_href_allowlist_domains"],
            ["reuters.com"],
        )

    def test_source_definition_enriches_trust_profile(self) -> None:
        source = SourceDefinition(
            name="Reuters",
            kind="rss",
            endpoint="https://www.reuters.com/world/rss",
            language="en",
        )
        self.assertEqual(source.tier, "tier1_media")
        self.assertEqual(source.confidence_level, "L2")
        self.assertGreaterEqual(source.trust_score, 0.85)
        self.assertEqual(source.metadata["source_confidence_level"], "L2")

    def test_selected_x_source_definition_resolves_to_l3(self) -> None:
        source = SourceDefinition(
            name="ReutersMarketsX",
            kind="rss",
            endpoint="https://rsshub.app/twitter/user/ReutersMarkets",
            language="en",
            tier="selected_x",
            tags=["selected_x", "x"],
        )
        self.assertEqual(source.tier, "selected_x")
        self.assertEqual(source.confidence_level, "L3")
        self.assertGreaterEqual(source.trust_score, 0.6)
        self.assertEqual(source.metadata["source_confidence_level"], "L3")

    def test_official_and_wire_mix_scores_high_and_verified(self) -> None:
        event = CanonicalNewsEvent(
            id="event-1",
            cluster_id="cluster-1",
            event_type="china_policy",
            bias="supportive",
            title="Policy update",
            summary="Policy update",
            normalized_text="pboc policy update",
            primary_language="en",
            source_languages=["en"],
            published_at="2026-03-21T00:00:00Z",
            regions=["China"],
            tags=["policy"],
            supporting_titles=["Policy update"],
            evidence_refs=[
                EvidenceRef(
                    source="PBOC",
                    source_tier="official",
                    title="PBOC release",
                    url="https://www.pbc.gov.cn/notice",
                    published_at="2026-03-21T00:00:00Z",
                    language="zh",
                ),
                EvidenceRef(
                    source="Reuters",
                    source_tier="tier1_media",
                    title="Reuters take",
                    url="https://www.reuters.com/example",
                    published_at="2026-03-21T00:05:00Z",
                    language="en",
                ),
            ],
        )
        score = CredibilityAgent().run([event])[0]
        self.assertTrue(score.verified)
        self.assertGreaterEqual(score.score, 0.85)
        self.assertEqual(score.tier, "high")

    def test_social_only_event_scores_low_and_unverified(self) -> None:
        event = CanonicalNewsEvent(
            id="event-2",
            cluster_id="cluster-2",
            event_type="macro_growth",
            bias="neutral",
            title="Rumor",
            summary="Rumor",
            normalized_text="rumor headline",
            primary_language="en",
            source_languages=["en"],
            published_at="2026-03-21T00:00:00Z",
            regions=["Global"],
            tags=["rumor"],
            supporting_titles=["Rumor"],
            evidence_refs=[
                EvidenceRef(
                    source="X",
                    source_tier="social",
                    title="Post",
                    url="https://x.com/post/1",
                    published_at="2026-03-21T00:00:00Z",
                    language="en",
                )
            ],
        )
        score = CredibilityAgent().run([event])[0]
        self.assertFalse(score.verified)
        self.assertLess(score.score, 0.55)
        self.assertIn("no_l1_l2_anchor", score.blocking_issues)

    def test_audit_requires_verified_flag(self) -> None:
        assessment = MarketImpactAssessment(
            id="impact-1",
            event_id="event-3",
            domain="equities",
            impacted_assets=["equities/csi300"],
            impacted_sectors=["banks"],
            direction="bullish",
            confidence=0.8,
            horizon="D0-D5",
            transmission_path=["policy", "rates", "equities"],
            key_evidence=[
                EvidenceRef(
                    source="Media",
                    source_tier="tier2_media",
                    title="Report",
                    url="https://example.com/report",
                    published_at="2026-03-21T00:00:00Z",
                    language="zh",
                )
            ],
            counter_evidence=[],
            watchlist=[],
            strategy_view="watch",
            downside_risks=[],
            status="draft",
            credibility_score=0.85,
        )
        score = CredibilityScore(
            event_id="event-3",
            score=0.9,
            verified=False,
            tier="high",
            rationale=["single L3 source"],
            blocking_issues=["unverified_source_mix"],
        )
        audited, notes = EvidenceAuditAgent(AuditSettings()).run([assessment], [score])
        self.assertEqual(audited[0].status, "watch_only")
        self.assertTrue(any("verified=False" in note for note in notes))


if __name__ == "__main__":
    unittest.main()

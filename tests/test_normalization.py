from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from news_employee.agents.normalize import NormalizationAgent
from news_employee.models import RawNewsItem


class NormalizationTests(unittest.TestCase):
    def test_bilingual_items_cluster_to_single_event(self) -> None:
        items = [
            RawNewsItem(
                id="en-1",
                source="sample",
                source_type="file",
                source_tier="tier1_media",
                language="en",
                title="Fed signals rates may stay higher for longer",
                summary="Federal Reserve officials kept a hawkish stance after strong CPI data.",
                url="https://example.com/en-1",
                published_at="2026-03-19T22:30:00Z",
                collected_at="2026-03-19T23:00:00Z",
            ),
            RawNewsItem(
                id="zh-1",
                source="sample",
                source_type="file",
                source_tier="tier1_media",
                language="zh",
                title="美联储偏鹰表态 利率或更久维持高位",
                summary="美国通胀偏强后，联储官员继续释放鹰派信号。",
                url="https://example.com/zh-1",
                published_at="2026-03-19T22:40:00Z",
                collected_at="2026-03-19T23:00:00Z",
            ),
        ]
        clusters = NormalizationAgent().run(items)
        self.assertEqual(len(clusters), 1)
        self.assertEqual(sorted(clusters[0].source_languages), ["en", "zh"])


if __name__ == "__main__":
    unittest.main()

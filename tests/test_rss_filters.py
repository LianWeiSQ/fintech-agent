from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fitech_agent.adapters.rss import RSSSourceAdapter
from fitech_agent.config import SourceDefinition
from fitech_agent.models import NewsWindow


class RSSSourceFilterTests(unittest.TestCase):
    @staticmethod
    def _mock_response(payload: str) -> MagicMock:
        response = MagicMock()
        response.__enter__.return_value.read.return_value = payload.encode("utf-8")
        response.__exit__.return_value = False
        return response

    @patch("fitech_agent.adapters.rss.urllib.request.urlopen")
    def test_rss_filters_by_author_and_keywords(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.return_value = self._mock_response(
            """
            <rss version="2.0">
              <channel>
                <item>
                  <title>China yield traders reassess Fed path</title>
                  <author>ReutersMarkets</author>
                  <link>https://x.com/ReutersMarkets/status/1</link>
                  <description>Bond markets react to policy repricing.</description>
                  <pubDate>Sat, 21 Mar 2026 08:00:00 GMT</pubDate>
                </item>
                <item>
                  <title>Podcast: weekend readout</title>
                  <author>ReutersMarkets</author>
                  <link>https://x.com/ReutersMarkets/status/2</link>
                  <description>Markets desk preview.</description>
                  <pubDate>Sat, 21 Mar 2026 09:00:00 GMT</pubDate>
                </item>
                <item>
                  <title>China yield traders reassess Fed path</title>
                  <author>OtherDesk</author>
                  <link>https://x.com/OtherDesk/status/3</link>
                  <description>Same topic from a different account.</description>
                  <pubDate>Sat, 21 Mar 2026 10:00:00 GMT</pubDate>
                </item>
              </channel>
            </rss>
            """
        )
        source = SourceDefinition(
            name="ReutersMarketsX",
            kind="rss",
            endpoint="https://rsshub.app/twitter/user/ReutersMarkets",
            language="en",
            tier="tier1_media",
            metadata={
                "author_allowlist": ["ReutersMarkets", "Reuters Markets"],
                "title_allowlist_keywords": ["china", "yield", "fed"],
                "title_blocklist_keywords": ["podcast"],
            },
        )
        window = NewsWindow(
            start="2026-03-21T00:00:00Z",
            end="2026-03-22T00:00:00Z",
        )

        items = RSSSourceAdapter(source).fetch(window, "2026-03-22T00:00:00Z")

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, "China yield traders reassess Fed path")
        self.assertEqual(items[0].metadata["entry_author"], "ReutersMarkets")

    @patch("fitech_agent.adapters.rss.urllib.request.urlopen")
    def test_rss_filters_by_summary_link_domains(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.return_value = self._mock_response(
            """
            <feed xmlns="http://www.w3.org/2005/Atom">
              <entry>
                <title>Fed pricing thread</title>
                <author><name>DeskCurator</name></author>
                <link href="https://example.com/curated/fed-pricing-thread" />
                <summary type="html">&lt;a href="https://www.reuters.com/markets/us/fed/"&gt;Reuters&lt;/a&gt;</summary>
                <updated>2026-03-21T12:00:00Z</updated>
              </entry>
              <entry>
                <title>Fed pricing thread</title>
                <author><name>DeskCurator</name></author>
                <link href="https://example.com/curated/fed-pricing-thread-2" />
                <summary type="html">&lt;a href="https://imgur.com/example"&gt;Imgur&lt;/a&gt;</summary>
                <updated>2026-03-21T13:00:00Z</updated>
              </entry>
            </feed>
            """
        )
        source = SourceDefinition(
            name="CuratedMacroDigest",
            kind="rss",
            endpoint="https://example.com/curated/fed.atom",
            language="en",
            tier="tier2_media",
            metadata={
                "title_allowlist_keywords": ["fed", "yield", "inflation"],
                "summary_href_allowlist_domains": ["reuters.com", "bloomberg.com"],
            },
        )
        window = NewsWindow(
            start="2026-03-21T00:00:00Z",
            end="2026-03-22T00:00:00Z",
        )

        items = RSSSourceAdapter(source).fetch(window, "2026-03-22T00:00:00Z")

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].metadata["entry_author"], "DeskCurator")
        self.assertEqual(
            items[0].metadata["summary_links"],
            ["https://www.reuters.com/markets/us/fed/"],
        )


if __name__ == "__main__":
    unittest.main()

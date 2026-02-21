"""Unit tests for NewsIngestor (sources.py)."""
import os
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

from src.ai.navigation.sources import NewsIngestor


RSS_SAMPLE = """<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <item>
      <title>Post-Quantum Update</title>
      <link>https://example.com/1</link>
      <description>ML-KEM standardized by NIST</description>
    </item>
    <item>
      <title>Mesh Network Benchmark</title>
      <link>https://example.com/2</link>
      <description>New MTTR record achieved</description>
    </item>
  </channel>
</rss>"""


class TestNewsIngestorInit:
    def test_default_feeds(self):
        ingestor = NewsIngestor()
        assert isinstance(ingestor.feeds, list)

    def test_custom_feeds(self):
        feeds = ["https://feed1.com/rss", "https://feed2.com/rss"]
        ingestor = NewsIngestor(feeds=feeds)
        assert ingestor.feeds == feeds

    def test_explicit_feeds_override(self):
        ingestor = NewsIngestor(feeds=["https://only.com/rss"])
        assert ingestor.feeds == ["https://only.com/rss"]


class TestParseRSS:
    def test_valid_rss(self):
        ingestor = NewsIngestor(feeds=[])
        items = ingestor._parse_rss(RSS_SAMPLE, "https://feed.example.com")
        assert len(items) == 2
        assert items[0]["title"] == "Post-Quantum Update"
        assert items[0]["url"] == "https://example.com/1"
        assert items[0]["source"] == "https://feed.example.com"

    def test_summary_truncation(self):
        long_desc = "A" * 1000
        rss = f"""<?xml version="1.0"?>
<rss version="2.0"><channel><item>
<title>T</title><description>{long_desc}</description>
</item></channel></rss>"""
        ingestor = NewsIngestor(feeds=[])
        items = ingestor._parse_rss(rss, "http://test.com")
        assert len(items[0]["summary"]) <= 500

    def test_invalid_xml(self):
        ingestor = NewsIngestor(feeds=[])
        items = ingestor._parse_rss("not xml at all", "http://test.com")
        assert items == []

    def test_missing_elements(self):
        rss = """<?xml version="1.0"?>
<rss version="2.0"><channel><item></item></channel></rss>"""
        ingestor = NewsIngestor(feeds=[])
        items = ingestor._parse_rss(rss, "http://test.com")
        assert len(items) == 1
        assert items[0]["title"] == "No Title"


class TestFetchFeed:
    @pytest.mark.asyncio
    async def test_success(self):
        ingestor = NewsIngestor(feeds=[])
        mock_session = MagicMock()
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.text = AsyncMock(return_value=RSS_SAMPLE)

        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=mock_resp)
        ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session.get = MagicMock(return_value=ctx)

        items = await ingestor.fetch_feed(mock_session, "https://feed.com/rss")
        assert len(items) == 2

    @pytest.mark.asyncio
    async def test_non_200(self):
        ingestor = NewsIngestor(feeds=[])
        mock_session = MagicMock()
        mock_resp = AsyncMock()
        mock_resp.status = 404

        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=mock_resp)
        ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session.get = MagicMock(return_value=ctx)

        items = await ingestor.fetch_feed(mock_session, "https://bad.com/rss")
        assert items == []

    @pytest.mark.asyncio
    async def test_exception(self):
        ingestor = NewsIngestor(feeds=[])
        mock_session = MagicMock()
        mock_session.get = MagicMock(side_effect=Exception("network error"))

        items = await ingestor.fetch_feed(mock_session, "https://error.com/rss")
        assert items == []

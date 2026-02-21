import asyncio
import aiohttp
import xml.etree.ElementTree as ET
from typing import List, Dict, Any
import logging

logger = logging.getLogger("AI-Navigator-Ingestor")

class NewsIngestor:
    """
    Ingests news from various asynchronous sources.
    Primarily focuses on RSS feeds for AI, Security, and Decentralization.
    """
    def __init__(self, feeds: List[str] = None):
        from .config import PROJECT_CONTEXT
        self.feeds = feeds or PROJECT_CONTEXT.get("sources", [])

    async def fetch_feed(self, session: aiohttp.ClientSession, url: str) -> List[Dict[str, str]]:
        """Fetch and parse a single RSS feed."""
        print(f"📡 Fetching: {url}...")
        try:
            async with session.get(url, timeout=10) as response:
                print(f"✅ Received response from {url}: {response.status}")
                if response.status != 200:
                    return []
                
                content = await response.text()
                return self._parse_rss(content, url)
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return []

    def _parse_rss(self, content: str, source_url: str) -> List[Dict[str, str]]:
        """Simple XML/RSS parser."""
        items = []
        try:
            root = ET.fromstring(content)
            # Handle RSS 2.0
            for item in root.findall(".//item"):
                title = item.find("title")
                link = item.find("link")
                summary = item.find("description")
                
                items.append({
                    "title": title.text if title is not None else "No Title",
                    "url": link.text if link is not None else source_url,
                    "summary": summary.text[:500] if summary is not None else "",
                    "source": source_url
                })
        except Exception as e:
            logger.warning(f"Failed to parse RSS from {source_url}: {e}")
        return items

    async def get_latest_news(self) -> List[Dict[str, str]]:
        """Fetch news from all configured feeds in parallel."""
        async with aiohttp.ClientSession() as session:
            tasks = [self.fetch_feed(session, url) for url in self.feeds]
            results = await asyncio.gather(*tasks)
            # Flatten list
            flat_list = [item for sublist in results for item in sublist]
            logger.info(f"Successfully ingested {len(flat_list)} items from {len(self.feeds)} feeds.")
            return flat_list

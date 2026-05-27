import logging
from typing import Dict, List
from urllib.parse import quote_plus

from src.ai.navigation.config import PROJECT_CONTEXT, SOURCES

logger = logging.getLogger("AI-Navigator-DeepSearch")

class DeepSearcher:
    """
    Performs deep web searches for specific high-value keywords 
    to supplement RSS feeds.
    """
    def __init__(self):
        self.keywords = PROJECT_CONTEXT.get("keywords", [])
        self.sources = SOURCES
        # Focus on top strategic keywords for deep search to avoid noise
        self.strategic_keywords = [
            "ML-KEM", "ML-DSA", "post-quantum mesh", 
            "eBPF packet bypass", "DAO governance model 2026",
            "self-healing network MTTR"
        ]

    async def perform_search(self, query: str) -> List[Dict[str, str]]:
        """
        Build source-backed deep-search candidates for a query.

        The navigator runs without API keys by default. Instead of returning an
        empty stub, it creates concrete search targets against curated sources
        so downstream filters and briefs can route high-value research work.
        """
        normalized_query = " ".join(query.split())
        if not normalized_query:
            return []

        encoded_query = quote_plus(normalized_query)
        results: List[Dict[str, str]] = []
        for source in self.sources:
            url_template = source.get("url_template", "")
            if not url_template:
                continue

            source_name = source.get("name", "source")
            results.append(
                {
                    "title": f"{normalized_query} research target: {source_name}",
                    "summary": source.get("summary", ""),
                    "url": url_template.format(query=encoded_query),
                    "source": source_name,
                    "query": normalized_query,
                }
            )

        logger.info("Prepared %d Deep Search targets for: %s", len(results), query)
        return results

    async def gather_intelligence(self) -> List[Dict[str, str]]:
        """Iterates through strategic keywords and finds news."""
        all_results = []
        seen_urls = set()
        for kw in self.strategic_keywords:
            results = await self.perform_search(kw)
            for item in results:
                url = item.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_results.append(item)
        return all_results

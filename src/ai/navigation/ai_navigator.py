from __future__ import annotations
import logging
import asyncio
from typing import List, Dict, Any
from datetime import datetime
try:
    from .config import PROJECT_CONTEXT, CRITERIA
except ImportError:
    from src.ai.navigation.config import PROJECT_CONTEXT, CRITERIA

logger = logging.getLogger(__name__)

class AINavigator:
    """
    AI Navigator Core.
    Filters AI news and technical updates to provide actionable steps.
    """

    def __init__(self, use_llm: bool = True):
        self.use_llm = use_llm
        self.context = PROJECT_CONTEXT
        self.criteria = CRITERIA

    async def filter_news(self, raw_news: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """
        Classifies and filters raw news items.
        
        Args:
            raw_news: List of news items with 'title', 'summary', 'url'.
            
        Returns:
            Filtered news items with 'category' and 'relevance_score'.
        """
        processed_news = []
        for item in raw_news:
            category = self._classify_item(item)
            relevance = self._calculate_relevance(item)
            
            if category != "GARBAGE":
                processed_news.append({
                    **item,
                    "category": category,
                    "relevance_score": relevance,
                    "timestamp": datetime.utcnow().isoformat()
                })
        
        # Sort by relevance
        processed_news.sort(key=lambda x: x["relevance_score"], reverse=True)
        return processed_news

    def _classify_item(self, item: Dict[str, str]) -> str:
        """Classify news with a deterministic local policy."""
        return self._simple_classifier(item)

    def _simple_classifier(self, item: Dict[str, str]) -> str:
        """Simple keyword-based classifier (fallback)."""
        text = (item.get("title", "") + " " + item.get("summary", "")).lower()
        
        # Check for benchmark keywords
        bench_keywords = ["sota", "benchmark", "performance", "record", "new release"]
        # Check for business keywords
        biz_keywords = ["launch", "acquisition", "funding", "market", "competitor", "sdk"]
        
        # Check against project context keywords
        context_keywords = self.context.get("keywords", [])
        
        found_context = any(self._keyword_matches(text, kw) for kw in context_keywords)
        
        if not found_context:
            return "GARBAGE"
            
        if any(kw in text for kw in biz_keywords):
            return "BUSINESS"
        if any(kw in text for kw in bench_keywords):
            return "BENCHMARK"
            
        return "BENCHMARK" # Default for context-related news

    def _calculate_relevance(self, item: Dict[str, str]) -> float:
        """Calculate relevance score (0.0 to 1.0) with word boundary awareness."""
        text = (item.get("title", "") + " " + item.get("summary", "")).lower()
        relevance = 0.0
        
        keywords = self.context.get("keywords", [])
        if not keywords:
            return 0.5
            
        matches = 0
        for kw in keywords:
            if self._keyword_matches(text, kw):
                matches += 1
                
        # Non-linear scoring: first match is most important
        if matches > 0:
            relevance = 0.4 + min(matches * 0.1, 0.6)
        
        return relevance

    @staticmethod
    def _keyword_matches(text: str, keyword: str) -> bool:
        import re

        normalized = keyword.lower()
        if len(normalized) <= 3 or normalized.replace("-", "").isalnum():
            pattern = rf"(?<![a-z0-9]){re.escape(normalized)}(?![a-z0-9])"
            return re.search(pattern, text) is not None
        return normalized in text

    async def generate_actionable_steps(self, filtered_news: List[Dict[str, Any]]) -> List[str]:
        """
        Translates news into actionable steps for the x0tta6bl4 project.
        """
        steps = []
        for item in filtered_news[:5]: # Take top 5
            title = item["title"]
            if item["category"] == "BUSINESS":
                if "funding" in title.lower() or "acquisition" in title.lower():
                    steps.append(f"MARKET WATCH: {title} - Monitor market shift and potential exit strategies.")
                else:
                    steps.append(f"STRATEGY: {title} - Evaluate as a potential partner or SDK integration target.")
            elif item["category"] == "BENCHMARK":
                if "accelerat" in title.lower() or "performance" in title.lower():
                    steps.append(f"EFFICIENCY: {title} - Audit our current architecture for similar bottlenecks.")
                else:
                    steps.append(f"TECH REVIEW: {title} - Deep dive into this technical advancement.")
        
        return steps

if __name__ == "__main__":
    # Quick Demo
    navigator = AINavigator()
    test_news = [
        {"title": "New NIST PQC Standard Finalized", "summary": "NIST has released FIPS 203, 204, and 205.", "url": "#"},
        {"title": "OpenAI releases new model", "summary": "A generic LLM update for chat.", "url": "#"},
        {"title": "Mesa Mesh Network gains 10k users", "summary": "A competitor mesh network is growing fast.", "url": "#"}
    ]
    
    async def run_demo():
        filtered = await navigator.filter_news(test_news)
        print(f"Filtered News: {len(filtered)}")
        for f in filtered:
            print(f"- [{f['category']}] {f['title']} (Score: {f['relevance_score']})")
        
        steps = await navigator.generate_actionable_steps(filtered)
        print("\nActionable Steps:")
        for s in steps:
            print(f"-> {s}")

    asyncio.run(run_demo())


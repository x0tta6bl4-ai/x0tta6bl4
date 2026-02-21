"""Unit tests for AI Navigation modules."""
import os
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

from src.ai.navigation.ai_navigator import AINavigator
from src.ai.navigation.brief_generator import BriefGenerator
from src.ai.navigation.deep_search import DeepSearcher


# --- AINavigator Tests ---

class TestAINavigatorInit:
    def test_defaults(self):
        nav = AINavigator()
        assert nav.use_llm is True
        assert isinstance(nav.context, dict)
        assert isinstance(nav.criteria, dict)

    def test_no_llm(self):
        nav = AINavigator(use_llm=False)
        assert nav.use_llm is False


class TestAINavigatorClassifier:
    def test_garbage_no_context_keywords(self):
        nav = AINavigator()
        item = {"title": "Cooking recipes 2026", "summary": "Best pasta dishes"}
        result = nav._simple_classifier(item)
        assert result == "GARBAGE"

    def test_business_category(self):
        nav = AINavigator()
        # Need context keywords + business keywords
        ctx_kw = nav.context.get("keywords", [])
        if ctx_kw:
            first_kw = ctx_kw[0]
            item = {
                "title": f"New funding round for {first_kw} project",
                "summary": f"Major acquisition in {first_kw} space",
            }
            result = nav._simple_classifier(item)
            assert result in ("BUSINESS", "BENCHMARK")

    def test_benchmark_category(self):
        nav = AINavigator()
        ctx_kw = nav.context.get("keywords", [])
        if ctx_kw:
            first_kw = ctx_kw[0]
            item = {
                "title": f"New SOTA performance for {first_kw}",
                "summary": f"Record benchmark in {first_kw}",
            }
            result = nav._simple_classifier(item)
            assert result in ("BUSINESS", "BENCHMARK")


class TestAINavigatorRelevance:
    def test_no_keywords_returns_half(self):
        nav = AINavigator()
        nav.context = {"keywords": []}
        item = {"title": "test", "summary": "test"}
        assert nav._calculate_relevance(item) == 0.5

    def test_matching_keyword_increases_score(self):
        nav = AINavigator()
        ctx_kw = nav.context.get("keywords", [])
        if ctx_kw:
            item = {
                "title": ctx_kw[0],
                "summary": " ".join(ctx_kw[:3]) if len(ctx_kw) >= 3 else ctx_kw[0],
            }
            score = nav._calculate_relevance(item)
            assert score > 0.0

    def test_no_match_returns_zero(self):
        nav = AINavigator()
        item = {"title": "zzzzunrelatedzzz", "summary": "qqqqnothingqqqq"}
        score = nav._calculate_relevance(item)
        assert score == 0.0


class TestAINavigatorAsync:
    @pytest.mark.asyncio
    async def test_filter_news_removes_garbage(self):
        nav = AINavigator()
        raw = [
            {"title": "Cooking tips", "summary": "How to boil water", "url": "#"},
        ]
        result = await nav.filter_news(raw)
        # Should be filtered out as GARBAGE
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_filter_news_sorted_by_relevance(self):
        nav = AINavigator()
        ctx_kw = nav.context.get("keywords", [])
        if not ctx_kw:
            pytest.skip("No context keywords configured")
        raw = [
            {"title": ctx_kw[0], "summary": "low match", "url": "#1"},
            {"title": " ".join(ctx_kw[:5]), "summary": " ".join(ctx_kw), "url": "#2"},
        ]
        result = await nav.filter_news(raw)
        if len(result) >= 2:
            assert result[0]["relevance_score"] >= result[1]["relevance_score"]

    @pytest.mark.asyncio
    async def test_generate_actionable_steps(self):
        nav = AINavigator()
        filtered = [
            {
                "title": "New PQC standard",
                "category": "BENCHMARK",
                "relevance_score": 0.9,
                "url": "#",
            },
            {
                "title": "Competitor funding round",
                "category": "BUSINESS",
                "relevance_score": 0.7,
                "url": "#",
            },
        ]
        steps = await nav.generate_actionable_steps(filtered)
        assert len(steps) == 2
        assert "TECH REVIEW" in steps[0] or "EFFICIENCY" in steps[0]
        assert "MARKET WATCH" in steps[1] or "STRATEGY" in steps[1]


# --- BriefGenerator Tests ---

class TestBriefGenerator:
    def test_init_default(self):
        gen = BriefGenerator()
        assert gen.project_name == "x0tta6bl4"

    def test_init_custom(self):
        gen = BriefGenerator(project_name="test-project")
        assert gen.project_name == "test-project"

    def test_generate_markdown_structure(self):
        gen = BriefGenerator()
        news = [
            {
                "category": "BENCHMARK",
                "title": "Test News",
                "url": "https://example.com",
                "relevance_score": 0.8,
            }
        ]
        actions = ["ACTION: Do something"]
        md = gen.generate_markdown(news, actions)
        assert "x0tta6bl4 Visionary Brief" in md
        assert "Filtered Intelligence" in md
        assert "Test News" in md
        assert "ACTION: Do something" in md
        assert "Key Action Items" in md

    def test_generate_markdown_empty(self):
        gen = BriefGenerator()
        md = gen.generate_markdown([], [])
        assert "Filtered Intelligence" in md

    def test_limits_to_five_items(self):
        gen = BriefGenerator()
        news = [
            {
                "category": "BENCHMARK",
                "title": f"News {i}",
                "url": "#",
                "relevance_score": 0.5,
            }
            for i in range(10)
        ]
        actions = [f"Action {i}" for i in range(10)]
        md = gen.generate_markdown(news, actions)
        # Table should have max 5 news rows
        assert "News 4" in md
        assert "News 5" not in md


# --- DeepSearcher Tests ---

class TestDeepSearcher:
    def test_init(self):
        ds = DeepSearcher()
        assert len(ds.strategic_keywords) > 0
        assert "ML-KEM" in ds.strategic_keywords

    @pytest.mark.asyncio
    async def test_perform_search_placeholder(self):
        ds = DeepSearcher()
        result = await ds.perform_search("test query")
        assert result == []

    @pytest.mark.asyncio
    async def test_gather_intelligence(self):
        ds = DeepSearcher()
        result = await ds.gather_intelligence()
        assert isinstance(result, list)

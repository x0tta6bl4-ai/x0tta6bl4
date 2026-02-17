"""Unit tests for MAPE-K Meta-Planning Phase."""
import os
import pytest
from unittest.mock import MagicMock, AsyncMock

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

from src.core.mape_k.meta_planning import MetaPlanner
from src.core.mape_k.models import ReasoningApproach, SolutionSpace, ReasoningPath


class TestMetaPlannerInit:
    def test_init_defaults(self):
        mp = MetaPlanner()
        assert mp.knowledge_base is None
        assert mp.graphsage is None
        assert mp.six_hats is None
        assert mp.first_principles is None

    def test_init_with_deps(self):
        mock = MagicMock()
        mp = MetaPlanner(knowledge_base=mock, graphsage=mock)
        assert mp.knowledge_base is mock
        assert mp.graphsage is mock


class TestMetaPlannerExecute:
    @pytest.mark.asyncio
    async def test_execute_minimal(self):
        mp = MetaPlanner()
        solution_space, reasoning_path = await mp.execute({"type": "cpu_overload"})
        assert isinstance(solution_space, SolutionSpace)
        assert isinstance(reasoning_path, ReasoningPath)
        assert solution_space.selected_approach is not None
        assert len(solution_space.approaches) >= 6

    @pytest.mark.asyncio
    async def test_execute_with_think_aloud(self):
        mock_think = MagicMock()
        mock_think.get_thoughts.return_value = []
        mp = MetaPlanner(think_aloud=mock_think)
        await mp.execute({"type": "test"})
        mock_think.log.assert_called()


class TestBuildApproaches:
    def test_default_approaches(self):
        mp = MetaPlanner()
        approaches = mp._build_approaches(None, None)
        assert len(approaches) == 6
        names = {a["name"] for a in approaches}
        assert ReasoningApproach.MAPE_K_ONLY.value in names
        assert ReasoningApproach.COMBINED_ALL.value in names

    def test_with_six_hats(self):
        mp = MetaPlanner()
        hats = {"green": {"creative_ideas": ["idea1", "idea2"]}}
        approaches = mp._build_approaches(hats, None)
        assert len(approaches) == 7
        assert any(a["name"] == "six_hats_creative" for a in approaches)

    def test_with_first_principles(self):
        mp = MetaPlanner()
        fp = {"fundamentals": ["f1", "f2", "f3"]}
        approaches = mp._build_approaches(None, fp)
        assert len(approaches) == 7
        assert any(a["name"] == "first_principles" for a in approaches)


class TestSelectBestApproach:
    def test_selects_highest_probability(self):
        mp = MetaPlanner()
        approaches = [
            {"name": "a", "probability": 0.5},
            {"name": "b", "probability": 0.9},
            {"name": "c", "probability": 0.7},
        ]
        probs = {"a": 0.5, "b": 0.9, "c": 0.7}
        best = mp._select_best_approach(approaches, probs)
        assert best["name"] == "b"

    def test_uses_external_probabilities(self):
        mp = MetaPlanner()
        approaches = [
            {"name": "a", "probability": 0.9},
            {"name": "b", "probability": 0.1},
        ]
        # Override with external probabilities
        probs = {"a": 0.1, "b": 0.99}
        best = mp._select_best_approach(approaches, probs)
        assert best["name"] == "b"


class TestFailureHistory:
    @pytest.mark.asyncio
    async def test_no_knowledge_base(self):
        mp = MetaPlanner()
        history = await mp._get_failure_history({"type": "test"})
        assert history == []

    @pytest.mark.asyncio
    async def test_with_knowledge_base(self):
        mock_kb = MagicMock()
        mock_kb.search_incidents = AsyncMock(return_value=[
            {"reasoning_analytics": {"algorithm_used": "rag"}, "meta_insight": {"why_it_failed": "timeout"}, "timestamp": "2026-01-01"},
        ])
        mp = MetaPlanner(knowledge_base=mock_kb)
        history = await mp._get_failure_history({"type": "test"})
        assert len(history) == 1
        assert history[0]["approach"] == "rag"


class TestCalculateProbabilities:
    @pytest.mark.asyncio
    async def test_fallback_probabilities(self):
        mp = MetaPlanner()
        approaches = [{"name": "a", "probability": 0.8}]
        probs = await mp._calculate_probabilities(approaches, {})
        assert probs["a"] == 0.8

    @pytest.mark.asyncio
    async def test_graphsage_probabilities(self):
        mock_gs = MagicMock()
        mock_prediction = MagicMock()
        mock_prediction.confidence = 0.95
        mock_gs.predict.return_value = mock_prediction
        mp = MetaPlanner(graphsage=mock_gs)
        approaches = [{"name": "a", "probability": 0.5}, {"name": "b", "probability": 0.6}]
        probs = await mp._calculate_probabilities(approaches, {"type": "test"})
        assert probs["a"] == 0.95
        assert probs["b"] == 0.95


class TestHelpers:
    def test_build_reasoning(self):
        mp = MetaPlanner()
        reasoning = mp._build_reasoning({"name": "a", "probability": 0.9}, {"a": 0.9})
        assert "0.90" in reasoning

    def test_estimate_time(self):
        mp = MetaPlanner()
        t = mp._estimate_time({"complexity": 0.5}, {"name": "a"})
        assert t == 1.5  # 1.0 * (1 + 0.5)

    def test_extract_features(self):
        mp = MetaPlanner()
        features = mp._extract_features({"type": "test"})
        assert "task_complexity" in features

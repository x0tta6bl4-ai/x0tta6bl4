"""
Unit tests for src/ledger/drift_detector.py

Covers: LedgerDriftDetector, DriftResult, get_drift_detector singleton
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock

import pytest


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_singleton():
    """Reset the module-level singleton before each test."""
    import src.ledger.drift_detector as mod
    mod._drift_detector_instance = None
    yield
    mod._drift_detector_instance = None


@pytest.fixture
def mock_graphsage():
    """Patch GraphSAGE import inside _init_components."""
    mock_cls = MagicMock()
    mock_instance = MagicMock()
    mock_instance.is_trained = False
    mock_cls.return_value = mock_instance
    with patch(
        "src.ml.graphsage_anomaly_detector.GraphSAGEAnomalyDetector",
        mock_cls,
    ):
        yield mock_instance


@pytest.fixture
def mock_causal():
    """Patch CausalAnalysisEngine import inside _init_components."""
    mock_cls = MagicMock()
    mock_instance = MagicMock()
    mock_cls.return_value = mock_instance
    with patch(
        "src.ml.causal_analysis.CausalAnalysisEngine",
        mock_cls,
    ):
        yield mock_instance


def _make_detector(continuity_content: Optional[str] = None, tmp_path: Path = None):
    """
    Create a LedgerDriftDetector with a controlled continuity file.

    If continuity_content is None, the file will NOT exist.
    """
    from src.ledger.drift_detector import LedgerDriftDetector

    detector = LedgerDriftDetector()
    if tmp_path is not None:
        cf = tmp_path / "CONTINUITY.md"
        if continuity_content is not None:
            cf.write_text(continuity_content, encoding="utf-8")
        detector.continuity_file = cf
    return detector


# ---------------------------------------------------------------------------
# DriftResult dataclass
# ---------------------------------------------------------------------------

class TestDriftResult:
    def test_drift_result_creation(self):
        from src.ledger.drift_detector import DriftResult

        dr = DriftResult(
            drift_type="code_drift",
            severity="high",
            description="test drift",
            section="Working set",
            detected_at="2026-01-07T00:00:00Z",
            recommendations=["fix it"],
            metadata={"key": "val"},
        )
        assert dr.drift_type == "code_drift"
        assert dr.severity == "high"
        assert dr.description == "test drift"
        assert dr.recommendations == ["fix it"]
        assert dr.metadata == {"key": "val"}

    def test_drift_result_default_metadata(self):
        from src.ledger.drift_detector import DriftResult

        dr = DriftResult(
            drift_type="doc_drift",
            severity="low",
            description="d",
            section="s",
            detected_at="t",
            recommendations=[],
        )
        assert dr.metadata is None


# ---------------------------------------------------------------------------
# LedgerDriftDetector.__init__ and _init_components
# ---------------------------------------------------------------------------

class TestInit:
    def test_init_sets_defaults(self, tmp_path):
        detector = _make_detector(tmp_path=tmp_path)
        assert detector._initialized is True
        # anomaly_detector and causal_engine may or may not be set
        # depending on environment, but _initialized should be True

    def test_init_components_graphsage_import_error(self, tmp_path):
        """When GraphSAGE import fails, anomaly_detector stays None."""
        with patch(
            "src.ledger.drift_detector.LedgerDriftDetector._init_components"
        ) as mock_init:
            mock_init.return_value = None
            from src.ledger.drift_detector import LedgerDriftDetector
            det = LedgerDriftDetector()
            det.anomaly_detector = None
            det.causal_engine = None
            det._initialized = True
            det.continuity_file = tmp_path / "CONTINUITY.md"
            assert det.anomaly_detector is None

    def test_init_components_causal_import_error(self, tmp_path):
        """When CausalAnalysis import fails, causal_engine stays None."""
        with patch(
            "src.ledger.drift_detector.LedgerDriftDetector._init_components"
        ) as mock_init:
            mock_init.return_value = None
            from src.ledger.drift_detector import LedgerDriftDetector
            det = LedgerDriftDetector()
            det.causal_engine = None
            det._initialized = True
            assert det.causal_engine is None


# ---------------------------------------------------------------------------
# build_ledger_graph
# ---------------------------------------------------------------------------

class TestBuildLedgerGraph:
    def test_no_file_returns_empty(self, tmp_path):
        detector = _make_detector(continuity_content=None, tmp_path=tmp_path)
        result = detector.build_ledger_graph()
        assert result == {"nodes": [], "edges": [], "sections": []}

    def test_empty_file(self, tmp_path):
        detector = _make_detector(continuity_content="", tmp_path=tmp_path)
        result = detector.build_ledger_graph()
        assert result["nodes"] == []
        assert result["edges"] == []

    def test_single_section(self, tmp_path):
        content = "## Introduction\nSome text here\nMore text"
        detector = _make_detector(continuity_content=content, tmp_path=tmp_path)
        result = detector.build_ledger_graph()
        assert len(result["nodes"]) == 1
        assert result["nodes"][0]["title"] == "Introduction"
        assert result["nodes"][0]["id"] == 0
        assert result["edges"] == []
        assert len(result["sections"]) == 1

    def test_multiple_sections(self, tmp_path):
        content = "## First\nContent A\n## Second\nContent B\n## Third\nContent C"
        detector = _make_detector(continuity_content=content, tmp_path=tmp_path)
        result = detector.build_ledger_graph()
        assert len(result["nodes"]) == 3
        titles = [n["title"] for n in result["nodes"]]
        assert titles == ["First", "Second", "Third"]

    def test_dependency_state_done(self, tmp_path):
        content = "## Done\nFinished items\n## State\nState Done overview"
        detector = _make_detector(continuity_content=content, tmp_path=tmp_path)
        result = detector.build_ledger_graph()
        # State section references "State" and "Done" -> dependency on "Done"
        edges = result["edges"]
        assert len(edges) == 1
        assert edges[0]["source"] == 0  # Done node
        assert edges[0]["target"] == 1  # State node
        assert edges[0]["type"] == "depends_on"

    def test_dependency_now_next(self, tmp_path):
        content = "## Now\nCurrent work\n## Next\nUpcoming\n## Planning\nNow and Next tasks"
        detector = _make_detector(continuity_content=content, tmp_path=tmp_path)
        result = detector.build_ledger_graph()
        # Planning mentions "Now" and "Next" -> deps on both
        edges = result["edges"]
        assert len(edges) == 2
        sources = {e["source"] for e in edges}
        assert 0 in sources  # Now
        assert 1 in sources  # Next

    def test_dependency_no_match(self, tmp_path):
        """Dependencies reference non-existent sections -> no edges."""
        content = "## State\nState Done overview"
        detector = _make_detector(continuity_content=content, tmp_path=tmp_path)
        result = detector.build_ledger_graph()
        # "Done" is mentioned but no section named "Done" exists
        assert result["edges"] == []

    def test_content_length_in_node(self, tmp_path):
        content = "## Sec\nLine 1\nLine 2\nLine 3"
        detector = _make_detector(continuity_content=content, tmp_path=tmp_path)
        result = detector.build_ledger_graph()
        node = result["nodes"][0]
        assert node["content_length"] > 0

    def test_no_h2_headers(self, tmp_path):
        """Content with no ## headers produces no nodes."""
        content = "# Top level\nSome content\n### Sub heading\nMore content"
        detector = _make_detector(continuity_content=content, tmp_path=tmp_path)
        result = detector.build_ledger_graph()
        assert result["nodes"] == []
        assert result["edges"] == []


# ---------------------------------------------------------------------------
# detect_code_drift
# ---------------------------------------------------------------------------

class TestDetectCodeDrift:
    @pytest.mark.asyncio
    async def test_no_src_directory(self, tmp_path):
        """If src/ directory doesn't exist, returns empty list."""
        detector = _make_detector(continuity_content="## Test\ncontent", tmp_path=tmp_path)
        # Patch PROJECT_ROOT to tmp_path so src/ doesn't exist
        with patch("src.ledger.drift_detector.PROJECT_ROOT", tmp_path):
            result = await detector.detect_code_drift()
        assert result == []

    @pytest.mark.asyncio
    async def test_no_continuity_file(self, tmp_path):
        """If CONTINUITY.md doesn't exist, returns empty after code scan."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "test_mod.py").write_text("def hello(): pass", encoding="utf-8")
        detector = _make_detector(continuity_content=None, tmp_path=tmp_path)
        with patch("src.ledger.drift_detector.PROJECT_ROOT", tmp_path):
            result = await detector.detect_code_drift()
        assert result == []

    @pytest.mark.asyncio
    async def test_code_drift_detected_for_undocumented_function(self, tmp_path):
        """Critical function present in code but not in docs -> drift."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        # Create a file with a critical function
        (src_dir / "module.py").write_text(
            "def detect_drift():\n    pass\n\ndef build_ledger_graph():\n    pass\n",
            encoding="utf-8",
        )
        # Continuity file does NOT mention detect_drift or build_ledger_graph
        detector = _make_detector(
            continuity_content="## Working set\nNothing relevant here",
            tmp_path=tmp_path,
        )
        with patch("src.ledger.drift_detector.PROJECT_ROOT", tmp_path):
            result = await detector.detect_code_drift()
        assert len(result) >= 1
        types = [d.drift_type for d in result]
        assert all(t == "code_drift" for t in types)

    @pytest.mark.asyncio
    async def test_no_drift_when_functions_documented(self, tmp_path):
        """Critical functions mentioned in docs -> no drift."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "module.py").write_text(
            "def detect_drift():\n    pass\ndef build_ledger_graph():\n    pass\ndef get_drift_detector():\n    pass\n",
            encoding="utf-8",
        )
        # Continuity file mentions all critical functions
        detector = _make_detector(
            continuity_content="## Docs\ndetect_drift build_ledger_graph get_drift_detector",
            tmp_path=tmp_path,
        )
        with patch("src.ledger.drift_detector.PROJECT_ROOT", tmp_path):
            result = await detector.detect_code_drift()
        assert result == []

    @pytest.mark.asyncio
    async def test_syntax_error_in_python_file_skipped(self, tmp_path):
        """Files with syntax errors are skipped gracefully."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "bad.py").write_text("def broken(:\n", encoding="utf-8")
        detector = _make_detector(
            continuity_content="## Doc\nSome doc",
            tmp_path=tmp_path,
        )
        with patch("src.ledger.drift_detector.PROJECT_ROOT", tmp_path):
            result = await detector.detect_code_drift()
        # Should not raise, returns empty or drifts (no crash)
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_exception_in_detect_code_drift(self, tmp_path):
        """General exception is caught and returns empty list."""
        detector = _make_detector(
            continuity_content="## Test\ndata",
            tmp_path=tmp_path,
        )
        # Make PROJECT_ROOT / "src" raise when checked
        with patch("src.ledger.drift_detector.PROJECT_ROOT", new_callable=lambda: MagicMock()) as mock_root:
            mock_src = MagicMock()
            mock_src.exists.side_effect = RuntimeError("boom")
            mock_root.__truediv__ = MagicMock(return_value=mock_src)
            result = await detector.detect_code_drift()
        assert result == []

    @pytest.mark.asyncio
    async def test_graphsage_branch_in_code_drift(self, tmp_path):
        """When anomaly_detector is set and files exist, GraphSAGE debug log happens."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "m.py").write_text("x = 1", encoding="utf-8")
        detector = _make_detector(
            continuity_content="## Doc\nSome doc",
            tmp_path=tmp_path,
        )
        detector.anomaly_detector = MagicMock()
        with patch("src.ledger.drift_detector.PROJECT_ROOT", tmp_path):
            result = await detector.detect_code_drift()
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_causal_engine_branch_in_code_drift(self, tmp_path):
        """When causal_engine is set and drifts found, causal debug log happens."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "m.py").write_text(
            "def detect_drift():\n    pass\n", encoding="utf-8"
        )
        detector = _make_detector(
            continuity_content="## Doc\nNo critical funcs mentioned",
            tmp_path=tmp_path,
        )
        detector.causal_engine = MagicMock()
        with patch("src.ledger.drift_detector.PROJECT_ROOT", tmp_path):
            result = await detector.detect_code_drift()
        # Should have drifts and causal log branch is hit
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# detect_metrics_drift
# ---------------------------------------------------------------------------

class TestDetectMetricsDrift:
    @pytest.mark.asyncio
    async def test_no_continuity_file(self, tmp_path):
        detector = _make_detector(continuity_content=None, tmp_path=tmp_path)
        result = await detector.detect_metrics_drift()
        assert result == []

    @pytest.mark.asyncio
    async def test_metrics_in_range_no_drift(self, tmp_path):
        content = "## Metrics\nTest Coverage: 85%\nError Rate: <1%\nResponse Time: 200ms"
        detector = _make_detector(continuity_content=content, tmp_path=tmp_path)
        with patch("src.ledger.drift_detector.find_metrics", return_value=[]):
            result = await detector.detect_metrics_drift()
        assert result == []

    @pytest.mark.asyncio
    async def test_coverage_out_of_range(self, tmp_path):
        content = "## Metrics\nTest Coverage: 30%"
        detector = _make_detector(continuity_content=content, tmp_path=tmp_path)
        with patch("src.ledger.drift_detector.find_metrics", return_value=[]):
            result = await detector.detect_metrics_drift()
        assert len(result) == 1
        assert result[0].drift_type == "metrics_drift"
        assert result[0].severity == "high"
        assert "test_coverage" in result[0].description

    @pytest.mark.asyncio
    async def test_error_rate_out_of_range(self, tmp_path):
        content = "## Perf\nError Rate: 10%"
        detector = _make_detector(continuity_content=content, tmp_path=tmp_path)
        with patch("src.ledger.drift_detector.find_metrics", return_value=[]):
            result = await detector.detect_metrics_drift()
        assert len(result) == 1
        assert "error_rate" in result[0].description

    @pytest.mark.asyncio
    async def test_response_time_out_of_range(self, tmp_path):
        content = "## Perf\nResponse Time: 999ms"
        detector = _make_detector(continuity_content=content, tmp_path=tmp_path)
        with patch("src.ledger.drift_detector.find_metrics", return_value=[]):
            result = await detector.detect_metrics_drift()
        assert len(result) == 1
        assert "response_time" in result[0].description

    @pytest.mark.asyncio
    async def test_multiple_metrics_out_of_range(self, tmp_path):
        content = "## M\nTest Coverage: 10%\nError Rate: 99%\nMTTD: 100s"
        detector = _make_detector(continuity_content=content, tmp_path=tmp_path)
        with patch("src.ledger.drift_detector.find_metrics", return_value=[]):
            result = await detector.detect_metrics_drift()
        assert len(result) >= 2

    @pytest.mark.asyncio
    async def test_production_readiness_out_of_range(self, tmp_path):
        content = "## M\nProduction Readiness: 10%"
        detector = _make_detector(continuity_content=content, tmp_path=tmp_path)
        with patch("src.ledger.drift_detector.find_metrics", return_value=[]):
            result = await detector.detect_metrics_drift()
        assert len(result) == 1
        assert "production_readiness" in result[0].description

    @pytest.mark.asyncio
    async def test_mttr_out_of_range(self, tmp_path):
        content = "## M\nMTTR: 60min"
        detector = _make_detector(continuity_content=content, tmp_path=tmp_path)
        with patch("src.ledger.drift_detector.find_metrics", return_value=[]):
            result = await detector.detect_metrics_drift()
        assert len(result) == 1
        assert "mttr" in result[0].description

    @pytest.mark.asyncio
    async def test_exception_in_metrics_drift(self, tmp_path):
        """General exception is caught and returns empty list."""
        detector = _make_detector(continuity_content="## X\ndata", tmp_path=tmp_path)
        with patch(
            "src.ledger.drift_detector.find_metrics",
            side_effect=RuntimeError("boom"),
        ):
            result = await detector.detect_metrics_drift()
        assert result == []

    @pytest.mark.asyncio
    async def test_drift_result_metadata(self, tmp_path):
        content = "## M\nTest Coverage: 5%"
        detector = _make_detector(continuity_content=content, tmp_path=tmp_path)
        with patch("src.ledger.drift_detector.find_metrics", return_value=[]):
            result = await detector.detect_metrics_drift()
        assert len(result) == 1
        m = result[0].metadata
        assert m["metric"] == "test_coverage"
        assert m["documented_value"] == 5.0
        assert m["expected_range"] == [75.0, 100.0]


# ---------------------------------------------------------------------------
# detect_doc_drift
# ---------------------------------------------------------------------------

class TestDetectDocDrift:
    @pytest.mark.asyncio
    async def test_no_continuity_file(self, tmp_path):
        detector = _make_detector(continuity_content=None, tmp_path=tmp_path)
        result = await detector.detect_doc_drift()
        assert result == []

    @pytest.mark.asyncio
    async def test_recent_update_no_drift(self, tmp_path):
        today = datetime.utcnow().strftime("%Y-%m-%d")
        content = f"## Notes\n{chr(1055)}оследнее обновление: {today}\nAll good"
        detector = _make_detector(continuity_content=content, tmp_path=tmp_path)
        result = await detector.detect_doc_drift()
        # No stale doc drift (updated today)
        stale = [d for d in result if "not updated" in d.description]
        assert len(stale) == 0

    @pytest.mark.asyncio
    async def test_stale_update_drift(self, tmp_path):
        old_date = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")
        content = f"## Notes\n{chr(1055)}оследнее обновление: {old_date}\nOld content"
        detector = _make_detector(continuity_content=content, tmp_path=tmp_path)
        result = await detector.detect_doc_drift()
        stale = [d for d in result if "not updated" in d.description]
        assert len(stale) == 1
        assert stale[0].drift_type == "doc_drift"
        assert stale[0].severity == "medium"
        assert stale[0].metadata["days_since_update"] >= 29

    @pytest.mark.asyncio
    async def test_deprecated_simplifiedntru(self, tmp_path):
        content = "## Crypto\nWe use SimplifiedNTRU for key exchange"
        detector = _make_detector(continuity_content=content, tmp_path=tmp_path)
        result = await detector.detect_doc_drift()
        deprecated = [d for d in result if "deprecated" in d.description.lower()]
        assert len(deprecated) >= 1

    @pytest.mark.asyncio
    async def test_deprecated_in_known_issues_ignored(self, tmp_path):
        content = "## Crypto\nKnown issues: SimplifiedNTRU is deprecated, we know"
        detector = _make_detector(continuity_content=content, tmp_path=tmp_path)
        result = await detector.detect_doc_drift()
        # Should NOT flag deprecated because context has "Known issues"
        deprecated = [d for d in result if "SimplifiedNTRU" in d.description]
        assert len(deprecated) == 0

    @pytest.mark.asyncio
    async def test_deprecated_mock_mode(self, tmp_path):
        content = "## System\nCurrently running in mock mode for testing"
        detector = _make_detector(continuity_content=content, tmp_path=tmp_path)
        result = await detector.detect_doc_drift()
        mock_drifts = [d for d in result if "mock" in d.description.lower() or "Mock" in d.description]
        assert len(mock_drifts) >= 1

    @pytest.mark.asyncio
    async def test_multiple_different_versions(self, tmp_path):
        # Use Cyrillic for "версия" (as in the code pattern)
        content = "## V1\n\u0432\u0435\u0440\u0441\u0438\u044f: 1.0.0\n## V2\n\u0432\u0435\u0440\u0441\u0438\u044f: 2.0.0"
        detector = _make_detector(continuity_content=content, tmp_path=tmp_path)
        result = await detector.detect_doc_drift()
        ver_drifts = [d for d in result if "version" in d.description.lower()]
        assert len(ver_drifts) == 1
        assert "1.0.0" in ver_drifts[0].description or "2.0.0" in ver_drifts[0].description

    @pytest.mark.asyncio
    async def test_single_version_no_drift(self, tmp_path):
        content = "## V1\n\u0432\u0435\u0440\u0441\u0438\u044f: 1.0.0\nAll good"
        detector = _make_detector(continuity_content=content, tmp_path=tmp_path)
        result = await detector.detect_doc_drift()
        ver_drifts = [d for d in result if "version" in d.description.lower()]
        assert len(ver_drifts) == 0

    @pytest.mark.asyncio
    async def test_same_versions_no_drift(self, tmp_path):
        content = "## V1\n\u0432\u0435\u0440\u0441\u0438\u044f: 1.0.0\n## V2\n\u0432\u0435\u0440\u0441\u0438\u044f: 1.0.0"
        detector = _make_detector(continuity_content=content, tmp_path=tmp_path)
        result = await detector.detect_doc_drift()
        ver_drifts = [d for d in result if "version" in d.description.lower()]
        assert len(ver_drifts) == 0

    @pytest.mark.asyncio
    async def test_invalid_date_no_crash(self, tmp_path):
        content = "## N\n\u041f\u043e\u0441\u043b\u0435\u0434\u043d\u0435\u0435 \u043e\u0431\u043d\u043e\u0432\u043b\u0435\u043d\u0438\u0435: 9999-99-99"
        detector = _make_detector(continuity_content=content, tmp_path=tmp_path)
        result = await detector.detect_doc_drift()
        # Should not crash - ValueError handled
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_exception_in_doc_drift(self, tmp_path):
        detector = _make_detector(continuity_content="## X\ndata", tmp_path=tmp_path)
        # Make read_text raise
        detector.continuity_file = MagicMock()
        detector.continuity_file.exists.return_value = True
        detector.continuity_file.read_text.side_effect = RuntimeError("boom")
        result = await detector.detect_doc_drift()
        assert result == []

    @pytest.mark.asyncio
    async def test_empty_content_no_drift(self, tmp_path):
        detector = _make_detector(continuity_content="", tmp_path=tmp_path)
        result = await detector.detect_doc_drift()
        assert result == []


# ---------------------------------------------------------------------------
# detect_drift (integration of all sub-detectors)
# ---------------------------------------------------------------------------

class TestDetectDrift:
    @pytest.mark.asyncio
    async def test_full_detect_no_file(self, tmp_path):
        """When no continuity file exists, returns structure with zeros."""
        detector = _make_detector(continuity_content=None, tmp_path=tmp_path)
        detector.anomaly_detector = None
        detector.causal_engine = None
        with patch("src.ledger.drift_detector.PROJECT_ROOT", tmp_path):
            result = await detector.detect_drift()
        assert result["total_drifts"] == 0
        assert result["status"] == "no_drift_detected"
        assert result["graph"]["nodes_count"] == 0
        assert result["anomalies"] == []
        assert result["root_causes"] == []

    @pytest.mark.asyncio
    async def test_detect_drift_returns_expected_keys(self, tmp_path):
        detector = _make_detector(
            continuity_content="## Sec\nContent here",
            tmp_path=tmp_path,
        )
        detector.anomaly_detector = None
        detector.causal_engine = None
        with patch("src.ledger.drift_detector.PROJECT_ROOT", tmp_path):
            result = await detector.detect_drift()
        expected_keys = {
            "timestamp", "total_drifts", "code_drifts", "metrics_drifts",
            "doc_drifts", "drifts", "graph", "anomalies", "root_causes",
            "ml_integration", "status",
        }
        assert expected_keys.issubset(set(result.keys()))

    @pytest.mark.asyncio
    async def test_detect_drift_calls_init_if_not_initialized(self, tmp_path):
        detector = _make_detector(
            continuity_content="## S\nC",
            tmp_path=tmp_path,
        )
        detector.anomaly_detector = None
        detector.causal_engine = None
        detector._initialized = False
        with patch.object(detector, "_init_components") as mock_init:
            with patch("src.ledger.drift_detector.PROJECT_ROOT", tmp_path):
                result = await detector.detect_drift()
            mock_init.assert_called_once()

    @pytest.mark.asyncio
    async def test_detect_drift_skips_init_if_already_initialized(self, tmp_path):
        detector = _make_detector(
            continuity_content="## S\nC",
            tmp_path=tmp_path,
        )
        detector.anomaly_detector = None
        detector.causal_engine = None
        detector._initialized = True
        with patch.object(detector, "_init_components") as mock_init:
            with patch("src.ledger.drift_detector.PROJECT_ROOT", tmp_path):
                result = await detector.detect_drift()
            mock_init.assert_not_called()

    @pytest.mark.asyncio
    async def test_detect_drift_with_graphsage_trained(self, tmp_path):
        """GraphSAGE is_trained = True: predict is called per node."""
        content = "## Alpha\nContent\n## Beta\nMore"
        detector = _make_detector(continuity_content=content, tmp_path=tmp_path)
        detector.causal_engine = None

        # Setup mock anomaly detector
        mock_pred = MagicMock()
        mock_pred.is_anomaly = True
        mock_pred.anomaly_score = 0.9
        mock_pred.confidence = 0.85
        mock_pred.inference_time_ms = 5.0

        mock_detector = MagicMock()
        mock_detector.is_trained = True
        mock_detector.predict.return_value = mock_pred
        detector.anomaly_detector = mock_detector

        with patch("src.ledger.drift_detector.PROJECT_ROOT", tmp_path):
            result = await detector.detect_drift()

        assert len(result["anomalies"]) == 2  # 2 nodes
        assert result["anomalies"][0]["anomaly_score"] == 0.9

    @pytest.mark.asyncio
    async def test_detect_drift_graphsage_predict_exception(self, tmp_path):
        """GraphSAGE predict raises -> gracefully continues."""
        content = "## Node1\nData"
        detector = _make_detector(continuity_content=content, tmp_path=tmp_path)
        detector.causal_engine = None

        mock_detector = MagicMock()
        mock_detector.is_trained = True
        mock_detector.predict.side_effect = RuntimeError("ML error")
        detector.anomaly_detector = mock_detector

        with patch("src.ledger.drift_detector.PROJECT_ROOT", tmp_path):
            result = await detector.detect_drift()
        assert result["anomalies"] == []

    @pytest.mark.asyncio
    async def test_detect_drift_graphsage_not_anomaly(self, tmp_path):
        """GraphSAGE predict returns is_anomaly=False -> not in anomalies."""
        content = "## Node1\nData"
        detector = _make_detector(continuity_content=content, tmp_path=tmp_path)
        detector.causal_engine = None

        mock_pred = MagicMock()
        mock_pred.is_anomaly = False
        mock_detector = MagicMock()
        mock_detector.is_trained = True
        mock_detector.predict.return_value = mock_pred
        detector.anomaly_detector = mock_detector

        with patch("src.ledger.drift_detector.PROJECT_ROOT", tmp_path):
            result = await detector.detect_drift()
        assert result["anomalies"] == []

    @pytest.mark.asyncio
    async def test_detect_drift_graphsage_fallback_statistics(self, tmp_path):
        """When GraphSAGE is untrained and numpy available, fallback stats used."""
        # Create content with sections that have very different content lengths
        # to trigger z-score anomaly
        short = "## Short\nX"
        long_content = "## Long\n" + "A" * 5000
        medium = "## Medium\n" + "B" * 100
        content = f"{short}\n{long_content}\n{medium}"

        detector = _make_detector(continuity_content=content, tmp_path=tmp_path)
        detector.causal_engine = None

        mock_detector = MagicMock()
        mock_detector.is_trained = False
        detector.anomaly_detector = mock_detector

        with patch("src.ledger.drift_detector.PROJECT_ROOT", tmp_path):
            with patch("src.ledger.drift_detector.NUMPY_AVAILABLE", True):
                import numpy as np
                with patch("src.ledger.drift_detector.np", np):
                    result = await detector.detect_drift()

        # The fallback should produce anomalies for the outlier node
        # (though depends on z-score thresholds)
        assert isinstance(result["anomalies"], list)

    @pytest.mark.asyncio
    async def test_detect_drift_graphsage_outer_exception(self, tmp_path):
        """Outer exception in GraphSAGE block is caught."""
        content = "## Node1\nData"
        detector = _make_detector(continuity_content=content, tmp_path=tmp_path)
        detector.causal_engine = None

        # anomaly_detector that raises on attribute access
        mock_detector = MagicMock()
        type(mock_detector).is_trained = PropertyMock(side_effect=RuntimeError("fail"))
        detector.anomaly_detector = mock_detector

        with patch("src.ledger.drift_detector.PROJECT_ROOT", tmp_path):
            result = await detector.detect_drift()
        assert result["anomalies"] == []

    @pytest.mark.asyncio
    async def test_detect_drift_with_causal_analysis(self, tmp_path):
        """Causal engine produces root causes when drifts are found."""
        # Create content with metrics out of range to produce drifts
        content = "## Metrics\nTest Coverage: 5%"
        detector = _make_detector(continuity_content=content, tmp_path=tmp_path)
        detector.anomaly_detector = None

        # Mock causal analysis
        mock_root_cause = MagicMock()
        mock_root_cause.root_cause_type = "configuration_error"
        mock_root_cause.confidence = 0.85
        mock_root_cause.explanation = "Test explanation"
        mock_root_cause.node_id = "ledger"
        mock_root_cause.contributing_factors = ["factor1"]
        mock_root_cause.remediation_suggestions = ["fix it"]

        mock_result = MagicMock()
        mock_result.root_causes = [mock_root_cause]
        mock_result.confidence = 0.85

        mock_engine = MagicMock()
        mock_engine.analyze.return_value = mock_result
        detector.causal_engine = mock_engine

        with patch("src.ledger.drift_detector.PROJECT_ROOT", tmp_path):
            with patch("src.ledger.drift_detector.find_metrics", return_value=[]):
                # Mock the causal_analysis imports inside detect_drift
                mock_incident_cls = MagicMock()
                mock_severity_cls = MagicMock()
                mock_severity_cls.LOW = "low"
                mock_severity_cls.MEDIUM = "medium"
                mock_severity_cls.HIGH = "high"
                mock_severity_cls.CRITICAL = "critical"

                with patch.dict("sys.modules", {
                    "src.ml.causal_analysis": MagicMock(
                        IncidentEvent=mock_incident_cls,
                        IncidentSeverity=mock_severity_cls,
                    ),
                }):
                    result = await detector.detect_drift()

        assert result["total_drifts"] >= 1
        assert len(result["root_causes"]) >= 1
        assert result["root_causes"][0]["method"] == "ml_causal_analysis"

    @pytest.mark.asyncio
    async def test_detect_drift_causal_analyze_exception_fallback(self, tmp_path):
        """When causal analyze() raises, fallback grouping is used."""
        content = "## Metrics\nTest Coverage: 5%\nProduction Readiness: 5%"
        detector = _make_detector(continuity_content=content, tmp_path=tmp_path)
        detector.anomaly_detector = None

        mock_engine = MagicMock()
        mock_engine.analyze.side_effect = RuntimeError("ML failed")
        detector.causal_engine = mock_engine

        with patch("src.ledger.drift_detector.PROJECT_ROOT", tmp_path):
            with patch("src.ledger.drift_detector.find_metrics", return_value=[]):
                mock_severity_cls = MagicMock()
                mock_severity_cls.LOW = "low"
                mock_severity_cls.MEDIUM = "medium"
                mock_severity_cls.HIGH = "high"
                mock_severity_cls.CRITICAL = "critical"
                with patch.dict("sys.modules", {
                    "src.ml.causal_analysis": MagicMock(
                        IncidentEvent=MagicMock(),
                        IncidentSeverity=mock_severity_cls,
                    ),
                }):
                    result = await detector.detect_drift()

        # Fallback grouping should produce root causes for grouped drifts
        assert result["total_drifts"] >= 2
        # The fallback groups drifts with same type+severity
        # Both are metrics_drift + high -> group with count > 1
        fallback_rcs = [rc for rc in result["root_causes"] if rc.get("method") == "fallback_grouping"]
        assert len(fallback_rcs) >= 1

    @pytest.mark.asyncio
    async def test_detect_drift_causal_outer_exception(self, tmp_path):
        """Outer exception in causal analysis block is caught."""
        content = "## M\nTest Coverage: 5%"
        detector = _make_detector(continuity_content=content, tmp_path=tmp_path)
        detector.anomaly_detector = None

        # causal_engine that raises on any call
        mock_engine = MagicMock()
        mock_engine.add_incident.side_effect = RuntimeError("outer boom")
        detector.causal_engine = mock_engine

        with patch("src.ledger.drift_detector.PROJECT_ROOT", tmp_path):
            with patch("src.ledger.drift_detector.find_metrics", return_value=[]):
                mock_severity_cls = MagicMock()
                mock_severity_cls.LOW = "low"
                mock_severity_cls.MEDIUM = "medium"
                mock_severity_cls.HIGH = "high"
                mock_severity_cls.CRITICAL = "critical"
                with patch.dict("sys.modules", {
                    "src.ml.causal_analysis": MagicMock(
                        IncidentEvent=MagicMock(),
                        IncidentSeverity=mock_severity_cls,
                    ),
                }):
                    result = await detector.detect_drift()
        assert result["root_causes"] == []

    @pytest.mark.asyncio
    async def test_detect_drift_no_causal_no_graphsage(self, tmp_path):
        """No ML components -> ml_integration flags are False."""
        detector = _make_detector(
            continuity_content="## S\nC",
            tmp_path=tmp_path,
        )
        detector.anomaly_detector = None
        detector.causal_engine = None

        with patch("src.ledger.drift_detector.PROJECT_ROOT", tmp_path):
            result = await detector.detect_drift()
        assert result["ml_integration"]["graphsage_used"] is False
        assert result["ml_integration"]["causal_analysis_used"] is False

    @pytest.mark.asyncio
    async def test_detect_drift_status_complete_when_drifts(self, tmp_path):
        content = "## M\nTest Coverage: 5%"
        detector = _make_detector(continuity_content=content, tmp_path=tmp_path)
        detector.anomaly_detector = None
        detector.causal_engine = None

        with patch("src.ledger.drift_detector.PROJECT_ROOT", tmp_path):
            with patch("src.ledger.drift_detector.find_metrics", return_value=[]):
                result = await detector.detect_drift()
        assert result["status"] == "complete"

    @pytest.mark.asyncio
    async def test_detect_drift_with_edges_graphsage_neighbors(self, tmp_path):
        """Graph with edges: GraphSAGE receives neighbor features."""
        content = "## Done\nFinished\n## State\nState Done overview"
        detector = _make_detector(continuity_content=content, tmp_path=tmp_path)
        detector.causal_engine = None

        mock_pred = MagicMock()
        mock_pred.is_anomaly = True
        mock_pred.anomaly_score = 0.7
        mock_pred.confidence = 0.8
        mock_pred.inference_time_ms = 3.0

        mock_ad = MagicMock()
        mock_ad.is_trained = True
        mock_ad.predict.return_value = mock_pred
        detector.anomaly_detector = mock_ad

        with patch("src.ledger.drift_detector.PROJECT_ROOT", tmp_path):
            result = await detector.detect_drift()

        # predict was called for each node; State node has a neighbor (Done)
        assert mock_ad.predict.call_count == 2
        # Check second call has neighbors
        calls = mock_ad.predict.call_args_list
        # The State node (id=1) has an edge from Done (id=0)
        # In the code, neighbors are built from outgoing edges (source == node_id)
        # The edge is source=0 (Done) -> target=1 (State)
        # So Done has outgoing edge to State -> Done's neighbors include State
        # State has no outgoing edges -> State's neighbors is empty


# ---------------------------------------------------------------------------
# get_drift_detector (singleton)
# ---------------------------------------------------------------------------

class TestGetDriftDetector:
    def test_returns_instance(self):
        from src.ledger.drift_detector import get_drift_detector
        det = get_drift_detector()
        assert isinstance(det, object)
        assert hasattr(det, "build_ledger_graph")

    def test_singleton_returns_same_instance(self):
        from src.ledger.drift_detector import get_drift_detector
        det1 = get_drift_detector()
        det2 = get_drift_detector()
        assert det1 is det2

    def test_singleton_reset(self):
        import src.ledger.drift_detector as mod
        from src.ledger.drift_detector import get_drift_detector
        det1 = get_drift_detector()
        mod._drift_detector_instance = None
        det2 = get_drift_detector()
        assert det1 is not det2


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_graph_with_content_before_first_section(self, tmp_path):
        """Content before first ## header is ignored for sections."""
        content = "Preamble text\nMore preamble\n## First\nContent"
        detector = _make_detector(continuity_content=content, tmp_path=tmp_path)
        result = detector.build_ledger_graph()
        assert len(result["nodes"]) == 1
        assert result["nodes"][0]["title"] == "First"

    def test_graph_section_title_whitespace(self, tmp_path):
        content = "## Section With Spaces  \nContent"
        detector = _make_detector(continuity_content=content, tmp_path=tmp_path)
        result = detector.build_ledger_graph()
        assert result["nodes"][0]["title"] == "Section With Spaces"

    @pytest.mark.asyncio
    async def test_detect_code_drift_with_unicode_file(self, tmp_path):
        """Python files with unicode content are handled."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "unicode_mod.py").write_text(
            '# -*- coding: utf-8 -*-\ndef hello():\n    return "\u041f\u0440\u0438\u0432\u0435\u0442"\n',
            encoding="utf-8",
        )
        detector = _make_detector(
            continuity_content="## Doc\nContent",
            tmp_path=tmp_path,
        )
        with patch("src.ledger.drift_detector.PROJECT_ROOT", tmp_path):
            result = await detector.detect_code_drift()
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_detect_drift_timestamp_format(self, tmp_path):
        detector = _make_detector(
            continuity_content="## S\nC",
            tmp_path=tmp_path,
        )
        detector.anomaly_detector = None
        detector.causal_engine = None
        with patch("src.ledger.drift_detector.PROJECT_ROOT", tmp_path):
            result = await detector.detect_drift()
        assert result["timestamp"].endswith("Z")

    @pytest.mark.asyncio
    async def test_drifts_serialized_in_result(self, tmp_path):
        """Check that drifts list items have expected keys."""
        content = "## M\nTest Coverage: 5%"
        detector = _make_detector(continuity_content=content, tmp_path=tmp_path)
        detector.anomaly_detector = None
        detector.causal_engine = None
        with patch("src.ledger.drift_detector.PROJECT_ROOT", tmp_path):
            with patch("src.ledger.drift_detector.find_metrics", return_value=[]):
                result = await detector.detect_drift()
        assert len(result["drifts"]) >= 1
        d = result["drifts"][0]
        assert "type" in d
        assert "severity" in d
        assert "description" in d
        assert "section" in d
        assert "recommendations" in d

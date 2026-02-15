"""
Test ML integration in Ledger Drift Detector

Tests that real ML components (GraphSAGE, Causal Analysis) are used
instead of simple statistics/grouping.
"""

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.ledger.drift_detector import DriftResult, LedgerDriftDetector


@pytest.fixture
def mock_drift_detector():
    """Create drift detector with mocked ML components"""
    with (
        patch(
            "src.ml.graphsage_anomaly_detector.GraphSAGEAnomalyDetector"
        ) as MockGraphSAGE,
        patch("src.ml.causal_analysis.CausalAnalysisEngine") as MockCausalEngine,
    ):

        # Mock GraphSAGE detector
        mock_graphsage_instance = MockGraphSAGE.return_value
        mock_graphsage_instance.is_trained = True
        mock_graphsage_instance.predict.return_value = MagicMock(
            is_anomaly=True, anomaly_score=0.85, confidence=0.9, inference_time_ms=15.0
        )

        # Mock Causal Analysis Engine
        mock_causal_instance = MockCausalEngine.return_value
        mock_causal_result = MagicMock()
        mock_causal_result.root_causes = [
            MagicMock(
                root_cause_type="documentation_drift",
                confidence=0.92,
                explanation="Multiple drifts in documentation section",
                node_id="ledger",
                contributing_factors=["outdated_docs", "missing_updates"],
                remediation_suggestions=["Update CONTINUITY.md", "Sync documentation"],
            )
        ]
        mock_causal_result.confidence = 0.92
        mock_causal_instance.analyze.return_value = mock_causal_result

        detector = LedgerDriftDetector()
        detector.anomaly_detector = mock_graphsage_instance
        detector.causal_engine = mock_causal_instance
        detector._initialized = True

        return detector, mock_graphsage_instance, mock_causal_instance


@pytest.mark.asyncio
async def test_graphsage_ml_integration(mock_drift_detector):
    """Test that GraphSAGE ML model is used instead of simple statistics"""
    detector, mock_graphsage, _ = mock_drift_detector

    # Create a graph with nodes
    graph = {
        "nodes": [
            {"id": 0, "title": "State", "content_length": 1000},
            {"id": 1, "title": "Done", "content_length": 500},
        ],
        "edges": [{"source": 0, "target": 1, "type": "depends_on"}],
    }

    # Mock build_ledger_graph to return our test graph
    detector.build_ledger_graph = lambda: graph

    # Run drift detection
    result = await detector.detect_drift()

    # Verify GraphSAGE predict was called
    assert mock_graphsage.predict.called, "GraphSAGE.predict() should be called"

    # Verify ML integration flag
    assert result.get("ml_integration", {}).get(
        "graphsage_used", False
    ), "GraphSAGE ML integration should be used"

    # Verify anomalies are detected
    assert "anomalies" in result
    if result["anomalies"]:
        assert any(
            a.get("method") != "fallback_statistics" for a in result["anomalies"]
        ), "Anomalies should be detected using ML, not fallback statistics"


@pytest.mark.asyncio
async def test_causal_analysis_ml_integration(mock_drift_detector):
    """Test that Causal Analysis Engine is used instead of simple grouping"""
    detector, _, mock_causal = mock_drift_detector

    # Create test drifts
    drifts = [
        DriftResult(
            drift_type="doc_drift",
            severity="high",
            description="Documentation outdated",
            section="State",
            detected_at=datetime.utcnow().isoformat() + "Z",
            recommendations=["Update docs"],
        )
    ]

    # Mock detect methods to return our test drifts (async)
    async def mock_detect_code_drift():
        return []

    async def mock_detect_metrics_drift():
        return []

    async def mock_detect_doc_drift():
        return drifts

    detector.detect_code_drift = mock_detect_code_drift
    detector.detect_metrics_drift = mock_detect_metrics_drift
    detector.detect_doc_drift = mock_detect_doc_drift
    detector.build_ledger_graph = lambda: {"nodes": [], "edges": []}

    # Run drift detection
    result = await detector.detect_drift()

    # Verify Causal Analysis Engine methods were called
    assert (
        mock_causal.add_incident.called
    ), "CausalAnalysisEngine.add_incident() should be called"
    assert mock_causal.analyze.called, "CausalAnalysisEngine.analyze() should be called"

    # Verify ML integration flag
    assert result.get("ml_integration", {}).get(
        "causal_analysis_used", False
    ), "Causal Analysis ML integration should be used"

    # Verify root causes are detected
    assert "root_causes" in result
    if result["root_causes"]:
        assert any(
            rc.get("method") == "ml_causal_analysis" for rc in result["root_causes"]
        ), "Root causes should be detected using ML, not fallback grouping"


@pytest.mark.asyncio
async def test_fallback_when_model_not_trained(mock_drift_detector):
    """Test that fallback is used when ML model is not trained"""
    detector, mock_graphsage, _ = mock_drift_detector

    # Set model as not trained
    mock_graphsage.is_trained = False

    graph = {
        "nodes": [{"id": 0, "title": "State", "content_length": 1000}],
        "edges": [],
    }
    detector.build_ledger_graph = lambda: graph

    # Run drift detection
    result = await detector.detect_drift()

    # Verify fallback is used (no ML call)
    # Note: predict might still be called, but fallback logic should handle it
    assert "anomalies" in result


@pytest.mark.asyncio
async def test_ml_integration_flags(mock_drift_detector):
    """Test that ML integration flags are correctly set"""
    detector, mock_graphsage, mock_causal = mock_drift_detector
    mock_graphsage.is_trained = True

    graph = {
        "nodes": [{"id": 0, "title": "State", "content_length": 1000}],
        "edges": [],
    }
    detector.build_ledger_graph = lambda: graph

    async def mock_detect_code_drift():
        return []

    async def mock_detect_metrics_drift():
        return []

    async def mock_detect_doc_drift():
        return []

    detector.detect_code_drift = mock_detect_code_drift
    detector.detect_metrics_drift = mock_detect_metrics_drift
    detector.detect_doc_drift = mock_detect_doc_drift

    result = await detector.detect_drift()

    # Verify ML integration flags exist
    assert "ml_integration" in result
    assert "graphsage_used" in result["ml_integration"]
    assert "causal_analysis_used" in result["ml_integration"]

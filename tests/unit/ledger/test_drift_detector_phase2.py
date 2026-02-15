#!/usr/bin/env python3
"""
Tests for Ledger Drift Detector Phase 2 implementation.

Tests the complete Phase 2 functionality including:
- Code drift detection
- Metrics drift detection
- Doc drift detection
- GraphSAGE integration
- Causal Analysis integration
"""

import asyncio
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from src.ledger.drift_detector import (DriftResult, LedgerDriftDetector,
                                       get_drift_detector)


class TestLedgerDriftDetectorPhase2:
    """Test cases for Phase 2 implementation."""

    @pytest.fixture
    def detector(self):
        """Create a LedgerDriftDetector instance."""
        return LedgerDriftDetector()

    @pytest.mark.asyncio
    async def test_detect_code_drift_basic(self, detector):
        """Test basic code drift detection."""
        drifts = await detector.detect_code_drift()

        assert isinstance(drifts, list)
        # Should return list (may be empty if no drifts found)
        for drift in drifts:
            assert isinstance(drift, DriftResult)
            assert drift.drift_type == "code_drift"
            assert drift.severity in ["low", "medium", "high", "critical"]
            assert drift.description
            assert drift.section
            assert drift.detected_at
            assert isinstance(drift.recommendations, list)

    @pytest.mark.asyncio
    async def test_detect_metrics_drift_basic(self, detector):
        """Test basic metrics drift detection."""
        drifts = await detector.detect_metrics_drift()

        assert isinstance(drifts, list)
        for drift in drifts:
            assert isinstance(drift, DriftResult)
            assert drift.drift_type == "metrics_drift"
            assert drift.severity in ["low", "medium", "high", "critical"]
            assert drift.description
            assert drift.section
            assert drift.detected_at
            assert isinstance(drift.recommendations, list)

    @pytest.mark.asyncio
    async def test_detect_doc_drift_basic(self, detector):
        """Test basic doc drift detection."""
        drifts = await detector.detect_doc_drift()

        assert isinstance(drifts, list)
        for drift in drifts:
            assert isinstance(drift, DriftResult)
            assert drift.drift_type == "doc_drift"
            assert drift.severity in ["low", "medium", "high", "critical"]
            assert drift.description
            assert drift.section
            assert drift.detected_at
            assert isinstance(drift.recommendations, list)

    @pytest.mark.asyncio
    async def test_detect_drift_complete(self, detector):
        """Test complete drift detection."""
        result = await detector.detect_drift()

        assert isinstance(result, dict)
        assert "timestamp" in result
        assert "total_drifts" in result
        assert "code_drifts" in result
        assert "metrics_drifts" in result
        assert "doc_drifts" in result
        assert "drifts" in result
        assert "graph" in result
        assert "status" in result

        assert isinstance(result["total_drifts"], int)
        assert isinstance(result["code_drifts"], int)
        assert isinstance(result["metrics_drifts"], int)
        assert isinstance(result["doc_drifts"], int)
        assert isinstance(result["drifts"], list)
        assert isinstance(result["graph"], dict)
        assert result["status"] in ["partial", "complete"]

        # Verify graph structure
        assert "nodes_count" in result["graph"]
        assert "edges_count" in result["graph"]

    def test_build_ledger_graph(self, detector):
        """Test ledger graph building."""
        graph = detector.build_ledger_graph()

        assert isinstance(graph, dict)
        assert "nodes" in graph
        assert "edges" in graph
        assert "sections" in graph

        assert isinstance(graph["nodes"], list)
        assert isinstance(graph["edges"], list)
        assert isinstance(graph["sections"], list)

        # Verify node structure
        if graph["nodes"]:
            node = graph["nodes"][0]
            assert "id" in node
            assert "title" in node
            assert "content_length" in node

    def test_get_drift_detector_singleton(self):
        """Test singleton pattern for drift detector."""
        detector1 = get_drift_detector()
        detector2 = get_drift_detector()

        assert detector1 is detector2
        assert isinstance(detector1, LedgerDriftDetector)

    @pytest.mark.asyncio
    async def test_detect_code_drift_with_ast(self, detector):
        """Test code drift detection with AST parsing."""
        drifts = await detector.detect_code_drift()

        # Should handle AST parsing without errors
        assert isinstance(drifts, list)
        # May find drifts or not, but should not crash

    @pytest.mark.asyncio
    async def test_detect_metrics_drift_with_parsing(self, detector):
        """Test metrics drift detection with metric parsing."""
        drifts = await detector.detect_metrics_drift()

        # Should handle metric parsing without errors
        assert isinstance(drifts, list)
        # May find drifts or not, but should not crash

    @pytest.mark.asyncio
    async def test_detect_doc_drift_with_date_check(self, detector):
        """Test doc drift detection with date checking."""
        drifts = await detector.detect_doc_drift()

        # Should handle date checking without errors
        assert isinstance(drifts, list)
        # May find drifts or not, but should not crash

    def test_drift_result_structure(self):
        """Test DriftResult dataclass structure."""
        drift = DriftResult(
            drift_type="test_drift",
            severity="medium",
            description="Test description",
            section="Test Section",
            detected_at="2026-01-07T00:00:00Z",
            recommendations=["Recommendation 1", "Recommendation 2"],
            metadata={"key": "value"},
        )

        assert drift.drift_type == "test_drift"
        assert drift.severity == "medium"
        assert drift.description == "Test description"
        assert drift.section == "Test Section"
        assert drift.detected_at == "2026-01-07T00:00:00Z"
        assert len(drift.recommendations) == 2
        assert drift.metadata == {"key": "value"}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

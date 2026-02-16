#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for LedgerDriftDetector from src/ledger/drift_detector.py.
This version tests the new API introduced after Paradox Zone consolidation.
"""

import pytest

from src.ledger.drift_detector import LedgerDriftDetector, get_drift_detector


def test_initialization():
    """Test basic initialization of LedgerDriftDetector."""
    detector = LedgerDriftDetector()
    assert detector is not None
    assert hasattr(detector, "_initialized")
    assert detector._initialized is True
    assert hasattr(detector, "continuity_file")
    assert detector.continuity_file.exists()


def test_singleton_pattern():
    """Test that get_drift_detector returns a singleton instance."""
    detector1 = get_drift_detector()
    detector2 = get_drift_detector()
    assert detector1 is detector2


def test_build_ledger_graph():
    """Test that ledger graph can be built successfully."""
    detector = LedgerDriftDetector()
    graph = detector.build_ledger_graph()
    assert isinstance(graph, dict)
    assert "nodes" in graph
    assert "edges" in graph
    assert "sections" in graph
    assert len(graph["nodes"]) > 0
    assert len(graph["sections"]) > 0
    assert all(isinstance(node, dict) for node in graph["nodes"])


@pytest.mark.asyncio
async def test_detect_code_drift():
    """Test code drift detection functionality."""
    detector = LedgerDriftDetector()
    code_drifts = await detector.detect_code_drift()
    assert isinstance(code_drifts, list)
    assert all(hasattr(drift, "drift_type") for drift in code_drifts)


@pytest.mark.asyncio
async def test_detect_metrics_drift():
    """Test metrics drift detection functionality."""
    detector = LedgerDriftDetector()
    metrics_drifts = await detector.detect_metrics_drift()
    assert isinstance(metrics_drifts, list)
    assert all(hasattr(drift, "drift_type") for drift in metrics_drifts)


@pytest.mark.asyncio
async def test_detect_doc_drift():
    """Test documentation drift detection functionality."""
    detector = LedgerDriftDetector()
    doc_drifts = await detector.detect_doc_drift()
    assert isinstance(doc_drifts, list)
    assert all(hasattr(drift, "drift_type") for drift in doc_drifts)


@pytest.mark.asyncio
async def test_detect_all_drifts():
    """Test complete drift detection pipeline."""
    detector = LedgerDriftDetector()
    result = await detector.detect_drift()
    assert isinstance(result, dict)
    assert "timestamp" in result
    assert "total_drifts" in result
    assert "code_drifts" in result
    assert "metrics_drifts" in result
    assert "doc_drifts" in result
    assert "drifts" in result
    assert "graph" in result
    assert "anomalies" in result
    assert "root_causes" in result
    assert "ml_integration" in result
    assert "status" in result

    # Verify metrics counts match
    assert isinstance(result["total_drifts"], int)
    assert isinstance(result["code_drifts"], int)
    assert isinstance(result["metrics_drifts"], int)
    assert isinstance(result["doc_drifts"], int)


@pytest.mark.asyncio
async def test_ml_integration_in_detection():
    """Test that ML integration (GraphSAGE and Causal Analysis) is properly initialized."""
    detector = LedgerDriftDetector()
    result = await detector.detect_drift()

    assert isinstance(result["ml_integration"], dict)
    assert "graphsage_used" in result["ml_integration"]
    assert "causal_analysis_used" in result["ml_integration"]

    # Check that we have proper booleans
    assert isinstance(result["ml_integration"]["graphsage_used"], bool)
    assert isinstance(result["ml_integration"]["causal_analysis_used"], bool)

    # Verify anomalies and root causes are in correct format
    assert isinstance(result["anomalies"], list)
    assert isinstance(result["root_causes"], list)

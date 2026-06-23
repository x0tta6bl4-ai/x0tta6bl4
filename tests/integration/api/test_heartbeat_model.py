"""Integration test: Go agent heartbeat fields match Python API model.

Tests that the Go agent's HeartbeatRequest JSON is compatible with
Python API's NodeHeartbeatRequest Pydantic model.
"""

import hashlib
import json
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database import Base, MeshInstance, MeshNode
from src.api.maas.models import NodeHeartbeatRequest


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class TestGoAgentHeartbeatCompatibility:
    """Verify Go agent heartbeat JSON is compatible with Python model."""

    def test_go_agent_basic_fields(self):
        """Go agent sends these fields — Python model must accept them."""
        go_payload = {
            "node_id": "x0t-test-123",
            "status": "healthy",
            "neighbors_count": 5,
            "routing_table_size": 10,
            "uptime": 3600.0,
            "cpu_usage": 25.5,
            "memory_usage": 60.2,
            "latency_ms": 15.3,
            "traffic_mbps": 12.5,
            "active_connections": 3,
            "dataplane_probe_target": "10.0.0.1:5000",
            "custom_metrics": {
                "pqc_sessions": 3,
                "ebpf_key_hits": 42,
            },
        }

        # This should parse without errors
        req = NodeHeartbeatRequest(**go_payload)
        assert req.node_id == "x0t-test-123"
        assert req.status == "healthy"
        assert req.neighbors_count == 5
        assert req.cpu_usage == 25.5
        assert req.custom_metrics["pqc_sessions"] == 3

    def test_go_agent_legacy_fields(self):
        """Go agent sends legacy fields — Python model must accept them."""
        go_payload = {
            "node_id": "x0t-test-456",
            "status": "healthy",
            "peers_total": 5,
            "peers_healthy": 4,
            "health_score": 0.8,
            "uptime_sec": 3600.0,
            "messages_sent": 1234,
            "messages_recv": 5678,
        }

        # Python model should accept these via Optional fields
        req = NodeHeartbeatRequest(**go_payload)
        assert req.node_id == "x0t-test-456"
        assert req.status == "healthy"

    def test_go_agent_mixed_fields(self):
        """Go agent sends both new and legacy fields."""
        go_payload = {
            "node_id": "x0t-test-789",
            "status": "degraded",
            "neighbors_count": 3,
            "uptime": 1800.0,
            "peers_total": 3,
            "health_score": 0.6,
            "custom_metrics": {"healing_events": 2},
        }

        req = NodeHeartbeatRequest(**go_payload)
        assert req.node_id == "x0t-test-789"
        assert req.status == "degraded"
        assert req.neighbors_count == 3

    def test_status_validation(self):
        """Python model validates status field."""
        for status in ["healthy", "degraded", "unhealthy"]:
            req = NodeHeartbeatRequest(node_id="test", status=status)
            assert req.status == status

        with pytest.raises(Exception):
            NodeHeartbeatRequest(node_id="test", status="invalid")

    def test_empty_heartbeat_rejected(self):
        """Python model rejects completely empty heartbeat."""
        with pytest.raises(Exception):
            NodeHeartbeatRequest()

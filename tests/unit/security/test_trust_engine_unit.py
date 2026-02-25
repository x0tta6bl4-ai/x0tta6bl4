"""Unit tests for TrustEvaluator (trust_engine.py)."""
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime, timedelta
from src.security.trust_engine import TrustEvaluator


def _make_db(attestation=None, node=None, suspicious_count=0):
    """Build a mock DB session that returns the given objects."""
    db = MagicMock()

    def query_side_effect(model):
        mock_q = MagicMock()
        name = getattr(model, "__name__", str(model))
        if "NodeBinaryAttestation" in name:
            mock_q.filter.return_value.order_by.return_value.first.return_value = attestation
        elif "MeshNode" in name:
            mock_q.filter.return_value.first.return_value = node
        elif "AuditLog" in name:
            mock_q.filter.return_value.filter.return_value.count.return_value = suspicious_count
            mock_q.filter.return_value.count.return_value = suspicious_count
        return mock_q

    db.query.side_effect = query_side_effect
    return db


class TestCalculateNodeTrust:
    def test_full_trust_verified_active_no_suspicious(self):
        attestation = MagicMock(status="verified")
        node = MagicMock(last_seen=datetime.utcnow(), status="active")
        db = _make_db(attestation=attestation, node=node, suspicious_count=0)
        evaluator = TrustEvaluator(db)
        score = evaluator.calculate_node_trust("node-1")
        assert score == 1.0

    def test_no_attestation_penalises_40pct(self):
        node = MagicMock(last_seen=datetime.utcnow(), status="active")
        db = _make_db(attestation=None, node=node, suspicious_count=0)
        evaluator = TrustEvaluator(db)
        score = evaluator.calculate_node_trust("node-1")
        assert abs(score - 0.6) < 1e-9

    def test_unverified_attestation_penalises_40pct(self):
        attestation = MagicMock(status="pending")
        node = MagicMock(last_seen=datetime.utcnow(), status="active")
        db = _make_db(attestation=attestation, node=node, suspicious_count=0)
        evaluator = TrustEvaluator(db)
        score = evaluator.calculate_node_trust("node-1")
        assert abs(score - 0.6) < 1e-9

    def test_stale_heartbeat_penalises_20pct(self):
        attestation = MagicMock(status="verified")
        node = MagicMock(
            last_seen=datetime.utcnow() - timedelta(minutes=10),
            status="active",
        )
        db = _make_db(attestation=attestation, node=node, suspicious_count=0)
        evaluator = TrustEvaluator(db)
        score = evaluator.calculate_node_trust("node-1")
        assert abs(score - 0.8) < 1e-9

    def test_degraded_status_extra_10pct_penalty(self):
        attestation = MagicMock(status="verified")
        node = MagicMock(
            last_seen=datetime.utcnow() - timedelta(minutes=10),
            status="degraded",
        )
        db = _make_db(attestation=attestation, node=node, suspicious_count=0)
        evaluator = TrustEvaluator(db)
        score = evaluator.calculate_node_trust("node-1")
        assert abs(score - 0.7) < 1e-9

    def test_unknown_node_penalises_30pct(self):
        attestation = MagicMock(status="verified")
        db = _make_db(attestation=attestation, node=None, suspicious_count=0)
        evaluator = TrustEvaluator(db)
        score = evaluator.calculate_node_trust("node-1")
        assert abs(score - 0.7) < 1e-9

    def test_suspicious_actions_reduce_score(self):
        attestation = MagicMock(status="verified")
        node = MagicMock(last_seen=datetime.utcnow(), status="active")
        db = _make_db(attestation=attestation, node=node, suspicious_count=2)
        evaluator = TrustEvaluator(db)
        score = evaluator.calculate_node_trust("node-1")
        assert abs(score - 0.9) < 1e-9

    def test_suspicious_actions_capped_at_30pct(self):
        attestation = MagicMock(status="verified")
        node = MagicMock(last_seen=datetime.utcnow(), status="active")
        db = _make_db(attestation=attestation, node=node, suspicious_count=100)
        evaluator = TrustEvaluator(db)
        score = evaluator.calculate_node_trust("node-1")
        assert score >= 0.7

    def test_score_never_below_zero(self):
        db = _make_db(attestation=None, node=None, suspicious_count=999)
        evaluator = TrustEvaluator(db)
        score = evaluator.calculate_node_trust("node-worst")
        assert score >= 0.0

    def test_score_never_above_one(self):
        attestation = MagicMock(status="verified")
        node = MagicMock(last_seen=datetime.utcnow(), status="active")
        db = _make_db(attestation=attestation, node=node, suspicious_count=0)
        evaluator = TrustEvaluator(db)
        score = evaluator.calculate_node_trust("node-1")
        assert score <= 1.0


class TestGetRoutingWeight:
    def test_routing_weight_is_trust_squared(self):
        attestation = MagicMock(status="verified")
        node = MagicMock(last_seen=datetime.utcnow(), status="active")
        db = _make_db(attestation=attestation, node=node, suspicious_count=0)
        evaluator = TrustEvaluator(db)
        trust = evaluator.calculate_node_trust("node-1")
        weight = evaluator.get_routing_weight("node-1")
        assert abs(weight - trust ** 2) < 1e-9

    def test_low_trust_exponentially_lower_weight(self):
        # trust=0.6 → weight=0.36 (less than trust linearly)
        attestation = MagicMock(status="pending")
        node = MagicMock(last_seen=datetime.utcnow(), status="active")
        db = _make_db(attestation=attestation, node=node, suspicious_count=0)
        evaluator = TrustEvaluator(db)
        weight = evaluator.get_routing_weight("node-1")
        trust = evaluator.calculate_node_trust("node-1")
        assert weight < trust

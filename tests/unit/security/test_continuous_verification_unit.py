"""
Unit tests for src.security.continuous_verification module.

Tests continuous verification strategies:
- IdentityVerificationStrategy
- DeviceVerificationStrategy
- NetworkVerificationStrategy
- SessionVerificationStrategy
- BehaviorVerificationStrategy
- ContinuousVerificationEngine
"""

import time
from unittest.mock import MagicMock, patch

import pytest

from src.security.continuous_verification import (BehaviorProfile,
                                                  BehaviorVerificationStrategy,
                                                  ContinuousVerificationEngine,
                                                  DeviceVerificationStrategy,
                                                  IdentityVerificationStrategy,
                                                  NetworkVerificationStrategy,
                                                  RiskLevel, Session,
                                                  SessionVerificationStrategy,
                                                  VerificationCheck,
                                                  VerificationResult,
                                                  VerificationType)

# ---------------------------------------------------------------------------
# Dataclass helpers
# ---------------------------------------------------------------------------


class TestVerificationCheck:
    """Tests for the VerificationCheck dataclass."""

    def test_to_dict_contains_all_fields(self):
        check = VerificationCheck(
            check_id="chk-1",
            type=VerificationType.IDENTITY,
            result=VerificationResult.PASSED,
            score=0.95,
            details="OK",
            timestamp=1000.0,
            duration_ms=1.5,
        )
        d = check.to_dict()
        assert d["check_id"] == "chk-1"
        assert d["type"] == "identity"
        assert d["result"] == "passed"
        assert d["score"] == 0.95
        assert d["details"] == "OK"
        assert d["timestamp"] == 1000.0
        assert d["duration_ms"] == 1.5

    def test_to_dict_enum_values_are_strings(self):
        check = VerificationCheck(
            check_id="chk-2",
            type=VerificationType.DEVICE,
            result=VerificationResult.DEGRADED,
            score=0.5,
            details="degraded",
        )
        d = check.to_dict()
        assert isinstance(d["type"], str)
        assert isinstance(d["result"], str)


class TestSession:
    """Tests for the Session dataclass."""

    def test_to_dict_contains_expected_keys(self):
        session = Session(
            session_id="sess-1",
            entity_id="node-a",
            created_at=100.0,
            last_verified_at=200.0,
            last_activity_at=200.0,
            verification_count=3,
            failed_verifications=1,
            risk_score=0.2,
            is_active=True,
            metadata={"foo": "bar"},
        )
        d = session.to_dict()
        assert d["session_id"] == "sess-1"
        assert d["entity_id"] == "node-a"
        assert d["created_at"] == 100.0
        assert d["last_verified_at"] == 200.0
        assert d["last_activity_at"] == 200.0
        assert d["verification_count"] == 3
        assert d["failed_verifications"] == 1
        assert d["risk_score"] == 0.2
        assert d["is_active"] is True
        # metadata is intentionally excluded from to_dict
        assert "metadata" not in d

    def test_default_values(self):
        session = Session(
            session_id="s",
            entity_id="e",
            created_at=0.0,
            last_verified_at=0.0,
            last_activity_at=0.0,
        )
        assert session.verification_count == 0
        assert session.failed_verifications == 0
        assert session.risk_score == 0.0
        assert session.is_active is True
        assert session.metadata == {}


class TestBehaviorProfile:
    """Tests for the BehaviorProfile dataclass."""

    def test_update_adds_hour(self):
        profile = BehaviorProfile(entity_id="node-1")
        # timestamp 3600 * 10 = hour 10 UTC
        profile.update("read", "/data", 3600 * 10)
        assert 10 in profile.typical_hours

    def test_update_adds_action_count(self):
        profile = BehaviorProfile(entity_id="node-1")
        profile.update("read", "/data", 1000.0)
        profile.update("read", "/data", 1001.0)
        profile.update("write", "/data", 1002.0)
        assert profile.typical_actions["read"] == 2
        assert profile.typical_actions["write"] == 1

    def test_update_adds_resource(self):
        profile = BehaviorProfile(entity_id="node-1")
        profile.update("read", "/data", 1000.0)
        assert "/data" in profile.typical_resources

    def test_update_computes_request_rate(self):
        profile = BehaviorProfile(entity_id="node-1")
        # Two requests 60 seconds apart => ~2 requests per 1 minute => rate ~2/min
        profile.update("a", "/r", 0.0)
        profile.update("a", "/r", 60.0)
        assert profile.avg_request_rate == pytest.approx(2.0, rel=0.01)

    def test_update_single_request_no_rate(self):
        profile = BehaviorProfile(entity_id="node-1")
        profile.update("a", "/r", 100.0)
        # Only one request, rate stays at default
        assert profile.avg_request_rate == 0.0


# ---------------------------------------------------------------------------
# Identity Verification Strategy
# ---------------------------------------------------------------------------


class TestIdentityVerificationStrategy:
    """Tests for IdentityVerificationStrategy."""

    def _make_session(self, entity_id="node-abc"):
        return Session(
            session_id="sess-id",
            entity_id=entity_id,
            created_at=time.time(),
            last_verified_at=time.time(),
            last_activity_at=time.time(),
        )

    def test_identity_match_passes(self):
        strategy = IdentityVerificationStrategy()
        session = self._make_session("node-abc")
        context = {"claimed_id": "node-abc"}
        check = strategy.verify(session, context)
        assert check.result == VerificationResult.PASSED
        assert check.score == 1.0
        assert check.type == VerificationType.IDENTITY

    def test_identity_match_passes_when_no_claimed_id(self):
        """When claimed_id is absent, it defaults to entity_id, so it passes."""
        strategy = IdentityVerificationStrategy()
        session = self._make_session("node-abc")
        check = strategy.verify(session, {})
        assert check.result == VerificationResult.PASSED
        assert check.score == 1.0

    def test_identity_mismatch_fails(self):
        strategy = IdentityVerificationStrategy()
        session = self._make_session("node-abc")
        context = {"claimed_id": "node-xyz"}
        check = strategy.verify(session, context)
        assert check.result == VerificationResult.FAILED
        assert check.score == 0.0
        assert "mismatch" in check.details.lower()

    def test_invalid_did_fails(self):
        strategy = IdentityVerificationStrategy()
        session = self._make_session("node-abc")
        context = {"did": "invalid-did-format"}
        check = strategy.verify(session, context)
        assert check.result == VerificationResult.FAILED
        assert check.score == 0.0
        assert "DID" in check.details

    def test_valid_did_passes(self):
        strategy = IdentityVerificationStrategy()
        session = self._make_session("node-abc")
        context = {"did": "did:mesh:node-abc"}
        check = strategy.verify(session, context)
        assert check.result == VerificationResult.PASSED
        assert check.score == 1.0

    def test_check_id_format(self):
        strategy = IdentityVerificationStrategy()
        session = self._make_session("node-abc")
        check = strategy.verify(session, {})
        assert check.check_id == "identity-sess-id"


# ---------------------------------------------------------------------------
# Device Verification Strategy
# ---------------------------------------------------------------------------


class TestDeviceVerificationStrategy:
    """Tests for DeviceVerificationStrategy."""

    def _make_session(self, device_fingerprint=None):
        metadata = {}
        if device_fingerprint:
            metadata["device_fingerprint"] = device_fingerprint
        return Session(
            session_id="sess-dev",
            entity_id="node-1",
            created_at=time.time(),
            last_verified_at=time.time(),
            last_activity_at=time.time(),
            metadata=metadata,
        )

    def test_fingerprint_match_passes(self):
        strategy = DeviceVerificationStrategy()
        session = self._make_session(device_fingerprint="fp-abc")
        context = {"device_fingerprint": "fp-abc", "device_trust_level": 80}
        check = strategy.verify(session, context)
        assert check.result == VerificationResult.PASSED
        assert check.score == 0.8

    def test_fingerprint_changed_fails(self):
        strategy = DeviceVerificationStrategy()
        session = self._make_session(device_fingerprint="fp-abc")
        context = {"device_fingerprint": "fp-DIFFERENT"}
        check = strategy.verify(session, context)
        assert check.result == VerificationResult.FAILED
        assert check.score == 0.0
        assert "fingerprint changed" in check.details.lower()

    def test_low_trust_degrades(self):
        strategy = DeviceVerificationStrategy()
        session = self._make_session()
        context = {"device_trust_level": 20}
        check = strategy.verify(session, context)
        assert check.result == VerificationResult.DEGRADED
        assert check.score == pytest.approx(0.2)

    def test_default_trust_passes(self):
        """Default trust_level is 50 (>=30), so it should pass."""
        strategy = DeviceVerificationStrategy()
        session = self._make_session()
        context = {}
        check = strategy.verify(session, context)
        assert check.result == VerificationResult.PASSED
        assert check.score == pytest.approx(0.5)

    def test_no_original_fingerprint_skips_check(self):
        """If no original fingerprint stored, fingerprint change check is skipped."""
        strategy = DeviceVerificationStrategy()
        session = self._make_session()  # no fingerprint in metadata
        context = {"device_fingerprint": "fp-new", "device_trust_level": 90}
        check = strategy.verify(session, context)
        assert check.result == VerificationResult.PASSED
        assert check.score == pytest.approx(0.9)

    def test_check_id_format(self):
        strategy = DeviceVerificationStrategy()
        session = self._make_session()
        check = strategy.verify(session, {})
        assert check.check_id == "device-sess-dev"


# ---------------------------------------------------------------------------
# Network Verification Strategy
# ---------------------------------------------------------------------------


class TestNetworkVerificationStrategy:
    """Tests for NetworkVerificationStrategy."""

    def _make_session(self, source_ip=None, country=None):
        metadata = {}
        if source_ip:
            metadata["source_ip"] = source_ip
        if country:
            metadata["country"] = country
        return Session(
            session_id="sess-net",
            entity_id="node-1",
            created_at=time.time(),
            last_verified_at=time.time(),
            last_activity_at=time.time(),
            metadata=metadata,
        )

    def test_same_ip_passes(self):
        strategy = NetworkVerificationStrategy()
        session = self._make_session(source_ip="10.0.0.1", country="US")
        context = {"source_ip": "10.0.0.1", "country": "US"}
        check = strategy.verify(session, context)
        assert check.result == VerificationResult.PASSED
        assert check.score == 1.0
        assert check.details == "Network context normal"

    def test_ip_change_degrades(self):
        strategy = NetworkVerificationStrategy()
        session = self._make_session(source_ip="10.0.0.1")
        context = {"source_ip": "192.168.1.1"}
        check = strategy.verify(session, context)
        assert check.score == pytest.approx(0.8)
        assert check.result == VerificationResult.PASSED  # 0.8 >= 0.8 => PASSED
        assert "IP changed" in check.details

    def test_country_change_degrades(self):
        strategy = NetworkVerificationStrategy()
        session = self._make_session(source_ip="10.0.0.1", country="US")
        context = {"source_ip": "10.0.0.1", "country": "RU"}
        check = strategy.verify(session, context)
        assert check.score == pytest.approx(0.7)
        assert check.result == VerificationResult.DEGRADED
        assert "Country changed" in check.details

    def test_ip_and_country_change_degrades_further(self):
        strategy = NetworkVerificationStrategy()
        session = self._make_session(source_ip="10.0.0.1", country="US")
        context = {"source_ip": "1.2.3.4", "country": "CN"}
        check = strategy.verify(session, context)
        # score = 1.0 - 0.2 (ip) - 0.3 (country) = 0.5
        assert check.score == pytest.approx(0.5)
        assert check.result == VerificationResult.DEGRADED

    def test_tor_detected(self):
        strategy = NetworkVerificationStrategy()
        session = self._make_session()
        context = {"is_tor": True}
        check = strategy.verify(session, context)
        assert check.score == pytest.approx(0.9)
        assert "Tor exit node" in check.details

    def test_proxy_detected(self):
        strategy = NetworkVerificationStrategy()
        session = self._make_session()
        context = {"is_proxy": True}
        check = strategy.verify(session, context)
        assert check.score == pytest.approx(0.9)
        assert "Proxy detected" in check.details

    def test_all_network_anomalies_combined(self):
        strategy = NetworkVerificationStrategy()
        session = self._make_session(source_ip="10.0.0.1", country="US")
        context = {
            "source_ip": "1.2.3.4",
            "country": "CN",
            "is_tor": True,
            "is_proxy": True,
        }
        # score = 1.0 - 0.2 - 0.3 - 0.1 - 0.1 = 0.3
        check = strategy.verify(session, context)
        assert check.score == pytest.approx(0.3)
        assert check.result == VerificationResult.FAILED  # < 0.5

    def test_no_original_ip_no_penalty(self):
        strategy = NetworkVerificationStrategy()
        session = self._make_session()  # no original IP
        context = {"source_ip": "10.0.0.1"}
        check = strategy.verify(session, context)
        assert check.score == 1.0
        assert check.result == VerificationResult.PASSED

    def test_check_id_format(self):
        strategy = NetworkVerificationStrategy()
        session = self._make_session()
        check = strategy.verify(session, {})
        assert check.check_id == "network-sess-net"


# ---------------------------------------------------------------------------
# Session Verification Strategy
# ---------------------------------------------------------------------------


class TestSessionVerificationStrategy:
    """Tests for SessionVerificationStrategy."""

    def _make_session(
        self, created_at, last_activity_at, verification_count=0, failed_verifications=0
    ):
        return Session(
            session_id="sess-sv",
            entity_id="node-1",
            created_at=created_at,
            last_verified_at=created_at,
            last_activity_at=last_activity_at,
            verification_count=verification_count,
            failed_verifications=failed_verifications,
        )

    @patch("src.security.continuous_verification.time")
    def test_fresh_session_passes(self, mock_time):
        now = 1000000.0
        mock_time.time.return_value = now
        strategy = SessionVerificationStrategy(max_idle_minutes=30, max_age_hours=24)
        session = self._make_session(
            created_at=now - 60,  # 1 minute old
            last_activity_at=now - 10,  # 10 seconds idle
        )
        check = strategy.verify(session, {})
        assert check.result == VerificationResult.PASSED
        assert check.score > 0.9

    @patch("src.security.continuous_verification.time")
    def test_expired_session_fails(self, mock_time):
        now = 1000000.0
        mock_time.time.return_value = now
        strategy = SessionVerificationStrategy(max_idle_minutes=30, max_age_hours=24)
        session = self._make_session(
            created_at=now - (25 * 3600),  # 25 hours old, exceeds 24h max
            last_activity_at=now - 10,
        )
        check = strategy.verify(session, {})
        assert check.result == VerificationResult.FAILED
        assert check.score == 0.0
        assert "expired" in check.details.lower()

    @patch("src.security.continuous_verification.time")
    def test_idle_session_fails(self, mock_time):
        now = 1000000.0
        mock_time.time.return_value = now
        strategy = SessionVerificationStrategy(max_idle_minutes=30, max_age_hours=24)
        session = self._make_session(
            created_at=now - 600,  # 10 minutes old
            last_activity_at=now - (31 * 60),  # 31 min idle, exceeds 30 min max
        )
        check = strategy.verify(session, {})
        assert check.result == VerificationResult.FAILED
        assert check.score == 0.0
        assert "idle" in check.details.lower()

    @patch("src.security.continuous_verification.time")
    def test_high_failure_rate_degrades(self, mock_time):
        now = 1000000.0
        mock_time.time.return_value = now
        strategy = SessionVerificationStrategy(max_idle_minutes=30, max_age_hours=24)
        session = self._make_session(
            created_at=now - 300,  # 5 min old
            last_activity_at=now - 10,
            verification_count=10,
            failed_verifications=5,  # 50% failure rate > 30%
        )
        check = strategy.verify(session, {})
        assert check.result == VerificationResult.DEGRADED
        assert check.score == pytest.approx(0.5)  # 1.0 - 0.5
        assert "failure rate" in check.details.lower()

    @patch("src.security.continuous_verification.time")
    def test_acceptable_failure_rate_passes(self, mock_time):
        now = 1000000.0
        mock_time.time.return_value = now
        strategy = SessionVerificationStrategy(max_idle_minutes=30, max_age_hours=24)
        session = self._make_session(
            created_at=now - 300,
            last_activity_at=now - 10,
            verification_count=10,
            failed_verifications=2,  # 20% < 30% threshold
        )
        check = strategy.verify(session, {})
        assert check.result == VerificationResult.PASSED

    @patch("src.security.continuous_verification.time")
    def test_custom_limits(self, mock_time):
        now = 1000000.0
        mock_time.time.return_value = now
        strategy = SessionVerificationStrategy(max_idle_minutes=5, max_age_hours=1)
        session = self._make_session(
            created_at=now - (2 * 3600),  # 2 hours old, exceeds 1h max
            last_activity_at=now - 10,
        )
        check = strategy.verify(session, {})
        assert check.result == VerificationResult.FAILED

    def test_check_id_format(self):
        strategy = SessionVerificationStrategy()
        session = self._make_session(
            created_at=time.time(),
            last_activity_at=time.time(),
        )
        check = strategy.verify(session, {})
        assert check.check_id == "session-sess-sv"


# ---------------------------------------------------------------------------
# Behavior Verification Strategy
# ---------------------------------------------------------------------------


class TestBehaviorVerificationStrategy:
    """Tests for BehaviorVerificationStrategy."""

    def _make_session(self, entity_id="node-1"):
        return Session(
            session_id="sess-beh",
            entity_id=entity_id,
            created_at=time.time(),
            last_verified_at=time.time(),
            last_activity_at=time.time(),
        )

    def test_normal_behavior_passes(self):
        """First verification with no historical profile should pass."""
        strategy = BehaviorVerificationStrategy()
        session = self._make_session()
        context = {"action": "read", "resource": "/data", "request_rate": 1.0}
        check = strategy.verify(session, context)
        assert check.result == VerificationResult.PASSED
        assert check.score == 1.0
        assert check.details == "Behavior normal"

    @patch("src.security.continuous_verification.time")
    def test_unusual_hour_degrades(self, mock_time):
        """Access at an unusual hour reduces score by 0.2."""
        strategy = BehaviorVerificationStrategy()
        session = self._make_session()

        # Build profile with typical hours
        profile = strategy.get_profile("node-1")
        profile.typical_hours = {9, 10, 11, 12, 13, 14, 15, 16, 17}

        # Current time in hour 3 (unusual)
        # time.time() % 86400 / 3600 = 3 => timestamp that produces hour 3
        mock_time.time.return_value = 3 * 3600 + 100  # hour 3 UTC
        context = {"action": "read", "resource": "/data"}
        check = strategy.verify(session, context)
        assert check.score == pytest.approx(0.8)
        assert "Unusual hour" in check.details

    def test_rare_action_degrades(self):
        strategy = BehaviorVerificationStrategy()
        session = self._make_session()

        # Build profile with 200 "read" actions
        profile = strategy.get_profile("node-1")
        profile.typical_actions = {"read": 200}

        context = {"action": "admin_delete", "resource": "/data"}
        check = strategy.verify(session, context)
        assert check.score <= 0.85  # -0.15 for rare action
        assert "Rare action" in check.details

    def test_high_request_rate_degrades(self):
        strategy = BehaviorVerificationStrategy()
        session = self._make_session()

        profile = strategy.get_profile("node-1")
        profile.avg_request_rate = 10.0  # normal: 10 req/min

        # Current rate is 60 req/min (6x normal, > 5x threshold)
        context = {"action": "read", "resource": "/data", "request_rate": 60.0}
        check = strategy.verify(session, context)
        assert check.score <= 0.7  # -0.3 for high rate
        assert "High request rate" in check.details

    def test_multiple_anomalies_can_fail(self):
        """When enough anomalies stack up, result is FAILED."""
        strategy = BehaviorVerificationStrategy()
        session = self._make_session()

        profile = strategy.get_profile("node-1")
        profile.typical_hours = {9, 10, 11}
        profile.typical_actions = {"read": 200}
        profile.avg_request_rate = 5.0

        # Unusual hour (current hour derived from time.time())
        with patch("src.security.continuous_verification.time") as mock_time:
            mock_time.time.return_value = 3 * 3600 + 50  # hour 3 (unusual)
            context = {
                "action": "admin_delete",  # rare action
                "resource": "/data",
                "request_rate": 100.0,  # 20x avg (exceeds 5x threshold)
            }
            check = strategy.verify(session, context)
            # -0.2 (hour) -0.15 (rare) -0.3 (rate) = 0.35 => FAILED
            assert check.result == VerificationResult.FAILED
            assert check.score == pytest.approx(0.35)

    def test_get_profile_creates_new(self):
        strategy = BehaviorVerificationStrategy()
        profile = strategy.get_profile("new-entity")
        assert profile.entity_id == "new-entity"
        assert profile.typical_hours == set()

    def test_get_profile_returns_existing(self):
        strategy = BehaviorVerificationStrategy()
        p1 = strategy.get_profile("node-1")
        p1.typical_hours.add(10)
        p2 = strategy.get_profile("node-1")
        assert 10 in p2.typical_hours
        assert p1 is p2

    def test_check_id_format(self):
        strategy = BehaviorVerificationStrategy()
        session = self._make_session()
        check = strategy.verify(session, {})
        assert check.check_id == "behavior-sess-beh"


# ---------------------------------------------------------------------------
# ContinuousVerificationEngine
# ---------------------------------------------------------------------------


class TestContinuousVerificationEngine:
    """Tests for ContinuousVerificationEngine."""

    def test_create_session(self):
        engine = ContinuousVerificationEngine(node_id="test-node")
        session = engine.create_session("entity-1", metadata={"source_ip": "10.0.0.1"})
        assert session.entity_id == "entity-1"
        assert session.is_active is True
        assert session.session_id in engine.sessions
        assert session.metadata["source_ip"] == "10.0.0.1"

    def test_create_session_default_metadata(self):
        engine = ContinuousVerificationEngine(node_id="test-node")
        session = engine.create_session("entity-1")
        assert session.metadata == {}

    def test_get_session(self):
        engine = ContinuousVerificationEngine(node_id="test-node")
        session = engine.create_session("entity-1")
        retrieved = engine.get_session(session.session_id)
        assert retrieved is session

    def test_get_session_nonexistent(self):
        engine = ContinuousVerificationEngine(node_id="test-node")
        assert engine.get_session("nonexistent") is None

    def test_terminate_session(self):
        engine = ContinuousVerificationEngine(node_id="test-node")
        session = engine.create_session("entity-1")
        result = engine.terminate_session(session.session_id)
        assert result is True
        assert session.is_active is False

    def test_terminate_nonexistent_session(self):
        engine = ContinuousVerificationEngine(node_id="test-node")
        result = engine.terminate_session("nonexistent")
        assert result is False

    def test_verify_session_returns_tuple(self):
        engine = ContinuousVerificationEngine(node_id="test-node")
        session = engine.create_session("entity-1")
        passed, checks, score = engine.verify_session(session.session_id)
        assert isinstance(passed, bool)
        assert isinstance(checks, list)
        assert isinstance(score, float)
        assert len(checks) > 0

    def test_verify_session_updates_counters(self):
        engine = ContinuousVerificationEngine(node_id="test-node")
        session = engine.create_session("entity-1")
        engine.verify_session(session.session_id)
        assert session.verification_count == 1

    def test_verify_session_nonexistent(self):
        engine = ContinuousVerificationEngine(node_id="test-node")
        passed, checks, score = engine.verify_session("nonexistent")
        assert passed is False
        assert checks == []
        assert score == 0.0

    def test_verify_session_terminated(self):
        engine = ContinuousVerificationEngine(node_id="test-node")
        session = engine.create_session("entity-1")
        engine.terminate_session(session.session_id)
        passed, checks, score = engine.verify_session(session.session_id)
        assert passed is False
        assert checks == []
        assert score == 0.0

    def test_verify_session_identity_pass(self):
        engine = ContinuousVerificationEngine(node_id="test-node")
        session = engine.create_session("entity-1")
        context = {"claimed_id": "entity-1"}
        passed, checks, score = engine.verify_session(
            session.session_id,
            context=context,
            check_types=[VerificationType.IDENTITY],
        )
        assert passed is True
        assert len(checks) == 1
        assert checks[0].result == VerificationResult.PASSED

    def test_verify_session_identity_fail(self):
        engine = ContinuousVerificationEngine(node_id="test-node")
        session = engine.create_session("entity-1")
        context = {"claimed_id": "entity-WRONG"}
        passed, checks, score = engine.verify_session(
            session.session_id,
            context=context,
            check_types=[VerificationType.IDENTITY],
        )
        assert passed is False
        assert checks[0].result == VerificationResult.FAILED
        assert session.failed_verifications == 1

    def test_verify_session_updates_risk_score(self):
        engine = ContinuousVerificationEngine(node_id="test-node")
        session = engine.create_session("entity-1")
        context = {"claimed_id": "entity-WRONG"}
        engine.verify_session(
            session.session_id,
            context=context,
            check_types=[VerificationType.IDENTITY],
        )
        # score = 0.0 => risk_score = 1.0 - 0.0 = 1.0
        assert session.risk_score == pytest.approx(1.0)

    def test_verify_session_with_specific_check_types(self):
        engine = ContinuousVerificationEngine(node_id="test-node")
        session = engine.create_session("entity-1")
        passed, checks, score = engine.verify_session(
            session.session_id,
            context={},
            check_types=[VerificationType.IDENTITY, VerificationType.DEVICE],
        )
        check_types = {c.type for c in checks}
        assert check_types == {VerificationType.IDENTITY, VerificationType.DEVICE}
        assert len(checks) == 2

    def test_verify_session_strategy_exception_handled(self):
        """If a strategy raises an exception, it's caught and recorded as FAILED."""
        engine = ContinuousVerificationEngine(node_id="test-node")
        session = engine.create_session("entity-1")

        # Replace identity strategy with one that raises
        broken = MagicMock()
        broken.verify.side_effect = RuntimeError("boom")
        engine.strategies[VerificationType.IDENTITY] = broken

        passed, checks, score = engine.verify_session(
            session.session_id,
            context={},
            check_types=[VerificationType.IDENTITY],
        )
        assert passed is False
        assert checks[0].result == VerificationResult.FAILED
        assert "Error" in checks[0].details

    def test_register_callback(self):
        engine = ContinuousVerificationEngine(node_id="test-node")
        callback_data = {}

        def my_callback(session, checks):
            callback_data["session_id"] = session.session_id
            callback_data["num_checks"] = len(checks)

        engine.register_callback(my_callback)
        session = engine.create_session("entity-1")
        engine.verify_session(
            session.session_id,
            context={},
            check_types=[VerificationType.IDENTITY],
        )
        assert callback_data["session_id"] == session.session_id
        assert callback_data["num_checks"] == 1

    def test_callback_exception_does_not_break_verification(self):
        engine = ContinuousVerificationEngine(node_id="test-node")

        def bad_callback(session, checks):
            raise ValueError("callback error")

        engine.register_callback(bad_callback)
        session = engine.create_session("entity-1")
        # Should not raise
        passed, checks, score = engine.verify_session(
            session.session_id,
            context={},
            check_types=[VerificationType.IDENTITY],
        )
        assert isinstance(passed, bool)

    def test_record_activity(self):
        engine = ContinuousVerificationEngine(node_id="test-node")
        session = engine.create_session("entity-1")
        old_activity = session.last_activity_at
        # Small sleep to ensure timestamp difference
        with patch("src.security.continuous_verification.time") as mock_time:
            mock_time.time.return_value = old_activity + 100.0
            engine.record_activity(session.session_id)
        assert session.last_activity_at == old_activity + 100.0

    def test_record_activity_nonexistent_session(self):
        engine = ContinuousVerificationEngine(node_id="test-node")
        # Should not raise
        engine.record_activity("nonexistent")

    def test_get_stats(self):
        engine = ContinuousVerificationEngine(
            node_id="test-node",
            base_interval_seconds=30,
            max_interval_seconds=120,
        )
        s1 = engine.create_session("entity-1")
        s2 = engine.create_session("entity-2")
        # Make s2 high risk
        s2.risk_score = 0.9

        stats = engine.get_stats()
        assert stats["total_sessions"] == 2
        assert stats["active_sessions"] == 2
        assert stats["high_risk_sessions"] == 1
        assert stats["background_running"] is False
        assert stats["base_interval"] == 30
        assert stats["max_interval"] == 120

    def test_get_stats_with_terminated_session(self):
        engine = ContinuousVerificationEngine(node_id="test-node")
        s1 = engine.create_session("entity-1")
        s2 = engine.create_session("entity-2")
        engine.terminate_session(s2.session_id)

        stats = engine.get_stats()
        assert stats["total_sessions"] == 2
        assert stats["active_sessions"] == 1

    def test_get_verification_interval_high_risk(self):
        engine = ContinuousVerificationEngine(
            node_id="test-node",
            base_interval_seconds=60,
            max_interval_seconds=300,
        )
        session = engine.create_session("entity-1")
        session.risk_score = 0.8  # > 0.7 => base_interval
        interval = engine.get_verification_interval(session)
        assert interval == 60

    def test_get_verification_interval_medium_risk(self):
        engine = ContinuousVerificationEngine(
            node_id="test-node",
            base_interval_seconds=60,
            max_interval_seconds=300,
        )
        session = engine.create_session("entity-1")
        session.risk_score = 0.5  # > 0.4, <= 0.7 => base * 2
        interval = engine.get_verification_interval(session)
        assert interval == 120

    def test_get_verification_interval_low_risk(self):
        engine = ContinuousVerificationEngine(
            node_id="test-node",
            base_interval_seconds=60,
            max_interval_seconds=300,
        )
        session = engine.create_session("entity-1")
        session.risk_score = 0.2  # <= 0.4 => max_interval
        interval = engine.get_verification_interval(session)
        assert interval == 300

    @patch("src.security.continuous_verification.time")
    def test_should_verify_true(self, mock_time):
        mock_time.time.return_value = 2000000.0
        engine = ContinuousVerificationEngine(
            node_id="test-node",
            base_interval_seconds=60,
            max_interval_seconds=300,
        )
        session = Session(
            session_id="s",
            entity_id="e",
            created_at=1000000.0,
            last_verified_at=1000000.0,  # verified long ago
            last_activity_at=2000000.0,
            risk_score=0.1,  # low risk => interval = 300s
        )
        # time since last = 2000000 - 1000000 = 1000000 >> 300
        assert engine.should_verify(session) is True

    @patch("src.security.continuous_verification.time")
    def test_should_verify_false(self, mock_time):
        now = 1000000.0
        mock_time.time.return_value = now
        engine = ContinuousVerificationEngine(
            node_id="test-node",
            base_interval_seconds=60,
            max_interval_seconds=300,
        )
        session = Session(
            session_id="s",
            entity_id="e",
            created_at=now - 10,
            last_verified_at=now - 10,  # verified 10 seconds ago
            last_activity_at=now,
            risk_score=0.1,  # low risk => interval = 300s
        )
        # time since last = 10 < 300
        assert engine.should_verify(session) is False

    def test_default_strategies_registered(self):
        engine = ContinuousVerificationEngine(node_id="test-node")
        assert VerificationType.IDENTITY in engine.strategies
        assert VerificationType.DEVICE in engine.strategies
        assert VerificationType.BEHAVIOR in engine.strategies
        assert VerificationType.NETWORK in engine.strategies
        assert VerificationType.SESSION in engine.strategies

"""
Unit tests for src.security.auto_isolation module.

Tests cover:
- IsolationRecord: expiry logic, to_dict serialization
- IsolationPolicy: duration calculation with escalation, level capping
- CircuitBreaker: state transitions CLOSED->OPEN->HALF_OPEN->CLOSED, allow_request
- AutoIsolationManager: isolate, escalation, release, get_isolation_level, is_allowed
- QuarantineZone: add/remove nodes, communication rules, operation allowance
"""

import time
from unittest.mock import MagicMock, patch

import pytest

from src.security.auto_isolation import (AutoIsolationManager, CircuitBreaker,
                                         IsolationLevel, IsolationPolicy,
                                         IsolationReason, IsolationRecord,
                                         QuarantineZone)


# ---------------------------------------------------------------------------
# IsolationRecord
# ---------------------------------------------------------------------------
class TestIsolationRecord:
    """Tests for IsolationRecord dataclass."""

    def _make_record(self, **overrides):
        defaults = dict(
            node_id="node-1",
            level=IsolationLevel.RESTRICTED,
            reason=IsolationReason.THREAT_DETECTED,
            started_at=1000.0,
            expires_at=2000.0,
        )
        defaults.update(overrides)
        return IsolationRecord(**defaults)

    def test_is_expired_returns_false_when_expires_at_is_none(self):
        record = self._make_record(expires_at=None)
        assert record.is_expired() is False

    def test_is_expired_returns_false_before_expiry(self):
        future = time.time() + 9999
        record = self._make_record(expires_at=future)
        assert record.is_expired() is False

    def test_is_expired_returns_true_after_expiry(self):
        past = time.time() - 1
        record = self._make_record(expires_at=past)
        assert record.is_expired() is True

    @patch("src.security.auto_isolation.time")
    def test_is_expired_boundary_with_mock(self, mock_time):
        """Verify expiry checks time.time() > expires_at (strictly greater)."""
        mock_time.time.return_value = 2000.0
        record = self._make_record(expires_at=2000.0)
        # time.time() == expires_at  -> NOT expired (needs strictly greater)
        assert record.is_expired() is False

        mock_time.time.return_value = 2000.1
        assert record.is_expired() is True

    def test_to_dict_contains_all_fields(self):
        record = self._make_record(
            escalation_count=2,
            details="test detail",
            auto_recover=False,
        )
        d = record.to_dict()
        assert d["node_id"] == "node-1"
        assert d["level"] == "RESTRICTED"
        assert d["reason"] == "threat_detected"
        assert d["started_at"] == 1000.0
        assert d["expires_at"] == 2000.0
        assert d["escalation_count"] == 2
        assert d["details"] == "test detail"
        assert d["auto_recover"] is False

    def test_to_dict_level_uses_name(self):
        for level in IsolationLevel:
            record = self._make_record(level=level)
            assert record.to_dict()["level"] == level.name

    def test_to_dict_reason_uses_value(self):
        for reason in IsolationReason:
            record = self._make_record(reason=reason)
            assert record.to_dict()["reason"] == reason.value

    def test_default_field_values(self):
        record = self._make_record()
        assert record.escalation_count == 0
        assert record.details == ""
        assert record.auto_recover is True
        assert record.recovery_conditions == []


# ---------------------------------------------------------------------------
# IsolationPolicy
# ---------------------------------------------------------------------------
class TestIsolationPolicy:
    """Tests for IsolationPolicy dataclass."""

    def _make_policy(self, **overrides):
        defaults = dict(
            name="test_policy",
            trigger_reason=IsolationReason.THREAT_DETECTED,
            initial_level=IsolationLevel.RESTRICTED,
            escalation_levels=[
                IsolationLevel.RESTRICTED,
                IsolationLevel.QUARANTINE,
                IsolationLevel.BLOCKED,
            ],
            escalation_threshold=2,
            initial_duration=300,
            escalation_multiplier=4.0,
            max_duration=86400,
            auto_recover=True,
        )
        defaults.update(overrides)
        return IsolationPolicy(**defaults)

    def test_get_duration_no_escalation(self):
        policy = self._make_policy(initial_duration=300, escalation_multiplier=4.0)
        assert policy.get_duration(0) == 300

    def test_get_duration_with_escalation(self):
        policy = self._make_policy(
            initial_duration=300, escalation_multiplier=2.0, max_duration=86400
        )
        # escalation_count=1 -> 300 * 2^1 = 600
        assert policy.get_duration(1) == 600
        # escalation_count=2 -> 300 * 2^2 = 1200
        assert policy.get_duration(2) == 1200

    def test_get_duration_capped_at_max(self):
        policy = self._make_policy(
            initial_duration=300,
            escalation_multiplier=10.0,
            max_duration=1000,
        )
        # 300 * 10^2 = 30000, should be capped to 1000
        assert policy.get_duration(2) == 1000

    def test_get_duration_returns_int(self):
        policy = self._make_policy(
            initial_duration=100, escalation_multiplier=1.5, max_duration=10000
        )
        result = policy.get_duration(1)
        assert isinstance(result, int)
        assert result == 150  # int(100 * 1.5)

    def test_get_level_returns_correct_level_for_index(self):
        levels = [
            IsolationLevel.RESTRICTED,
            IsolationLevel.QUARANTINE,
            IsolationLevel.BLOCKED,
        ]
        policy = self._make_policy(escalation_levels=levels)
        assert policy.get_level(0) == IsolationLevel.RESTRICTED
        assert policy.get_level(1) == IsolationLevel.QUARANTINE
        assert policy.get_level(2) == IsolationLevel.BLOCKED

    def test_get_level_caps_at_last_level(self):
        levels = [
            IsolationLevel.RATE_LIMIT,
            IsolationLevel.RESTRICTED,
        ]
        policy = self._make_policy(escalation_levels=levels)
        # Beyond index range should return last
        assert policy.get_level(2) == IsolationLevel.RESTRICTED
        assert policy.get_level(10) == IsolationLevel.RESTRICTED

    def test_get_level_single_level(self):
        policy = self._make_policy(escalation_levels=[IsolationLevel.QUARANTINE])
        assert policy.get_level(0) == IsolationLevel.QUARANTINE
        assert policy.get_level(5) == IsolationLevel.QUARANTINE


# ---------------------------------------------------------------------------
# CircuitBreaker
# ---------------------------------------------------------------------------
class TestCircuitBreaker:
    """Tests for CircuitBreaker state machine."""

    def test_initial_state_is_closed(self):
        cb = CircuitBreaker()
        assert cb.state == CircuitBreaker.State.CLOSED

    def test_allow_request_when_closed(self):
        cb = CircuitBreaker()
        assert cb.allow_request() is True

    def test_stays_closed_below_threshold(self):
        cb = CircuitBreaker(failure_threshold=5)
        for _ in range(4):
            cb.record_failure()
        assert cb.state == CircuitBreaker.State.CLOSED
        assert cb.allow_request() is True

    def test_opens_at_failure_threshold(self):
        cb = CircuitBreaker(failure_threshold=3)
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitBreaker.State.OPEN

    def test_allow_request_returns_false_when_open(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=60)
        cb.record_failure()
        assert cb.state == CircuitBreaker.State.OPEN
        assert cb.allow_request() is False

    @patch("src.security.auto_isolation.time")
    def test_transitions_to_half_open_after_recovery_timeout(self, mock_time):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=60)

        # Record failure at t=100
        mock_time.time.return_value = 100.0
        cb.record_failure()
        assert cb.state == CircuitBreaker.State.OPEN

        # Before timeout: t=159
        mock_time.time.return_value = 159.0
        assert cb.allow_request() is False
        assert cb.state == CircuitBreaker.State.OPEN

        # At recovery timeout: t=160
        mock_time.time.return_value = 160.0
        assert cb.allow_request() is True
        assert cb.state == CircuitBreaker.State.HALF_OPEN

    def test_allow_request_returns_true_when_half_open(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0)
        cb.record_failure()
        assert cb.state == CircuitBreaker.State.OPEN
        # recovery_timeout=0 so allow_request transitions immediately
        assert cb.allow_request() is True
        assert cb.state == CircuitBreaker.State.HALF_OPEN

    @patch("src.security.auto_isolation.time")
    def test_half_open_to_closed_on_enough_successes(self, mock_time):
        mock_time.time.return_value = 100.0
        cb = CircuitBreaker(
            failure_threshold=1,
            recovery_timeout=10,
            half_open_requests=3,
        )
        cb.record_failure()

        # Transition to HALF_OPEN
        mock_time.time.return_value = 200.0
        cb.allow_request()
        assert cb.state == CircuitBreaker.State.HALF_OPEN

        # Record successes
        cb.record_success()
        assert cb.state == CircuitBreaker.State.HALF_OPEN
        cb.record_success()
        assert cb.state == CircuitBreaker.State.HALF_OPEN
        cb.record_success()
        # Third success should close the breaker
        assert cb.state == CircuitBreaker.State.CLOSED
        assert cb.failure_count == 0
        assert cb.half_open_successes == 0

    @patch("src.security.auto_isolation.time")
    def test_half_open_to_open_on_failure(self, mock_time):
        mock_time.time.return_value = 100.0
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=10)
        cb.record_failure()

        # Transition to HALF_OPEN
        mock_time.time.return_value = 200.0
        cb.allow_request()
        assert cb.state == CircuitBreaker.State.HALF_OPEN

        # Failure during HALF_OPEN -> back to OPEN
        mock_time.time.return_value = 201.0
        cb.record_failure()
        assert cb.state == CircuitBreaker.State.OPEN

    def test_record_success_decrements_failure_count_when_closed(self):
        cb = CircuitBreaker(failure_threshold=5)
        cb.record_failure()
        cb.record_failure()
        assert cb.failure_count == 2
        cb.record_success()
        assert cb.failure_count == 1
        cb.record_success()
        assert cb.failure_count == 0
        # Should not go below 0
        cb.record_success()
        assert cb.failure_count == 0

    def test_full_lifecycle_closed_open_halfopen_closed(self):
        """Full circuit breaker lifecycle test."""
        cb = CircuitBreaker(
            failure_threshold=2,
            recovery_timeout=0,
            half_open_requests=1,
        )

        # CLOSED
        assert cb.state == CircuitBreaker.State.CLOSED
        assert cb.allow_request() is True

        # CLOSED -> OPEN
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitBreaker.State.OPEN

        # OPEN -> HALF_OPEN (recovery_timeout=0)
        assert cb.allow_request() is True
        assert cb.state == CircuitBreaker.State.HALF_OPEN

        # HALF_OPEN -> CLOSED (1 success needed)
        cb.record_success()
        assert cb.state == CircuitBreaker.State.CLOSED
        assert cb.allow_request() is True


# ---------------------------------------------------------------------------
# AutoIsolationManager
# ---------------------------------------------------------------------------
class TestAutoIsolationManager:
    """Tests for AutoIsolationManager."""

    def _make_manager(self, node_id="manager-node"):
        return AutoIsolationManager(node_id=node_id)

    def test_initial_state(self):
        mgr = self._make_manager()
        assert mgr.node_id == "manager-node"
        assert len(mgr.isolated_nodes) == 0

    def test_isolate_creates_record(self):
        mgr = self._make_manager()
        record = mgr.isolate(
            "target-1", IsolationReason.THREAT_DETECTED, details="test"
        )
        assert record.node_id == "target-1"
        assert record.reason == IsolationReason.THREAT_DETECTED
        assert record.details == "test"
        assert (
            record.level == IsolationLevel.RESTRICTED
        )  # initial level from default policy
        assert "target-1" in mgr.isolated_nodes

    def test_isolate_with_level_override(self):
        mgr = self._make_manager()
        record = mgr.isolate(
            "target-1",
            IsolationReason.THREAT_DETECTED,
            level_override=IsolationLevel.BLOCKED,
        )
        assert record.level == IsolationLevel.BLOCKED

    def test_isolate_with_duration_override(self):
        mgr = self._make_manager()
        before = time.time()
        record = mgr.isolate(
            "target-1",
            IsolationReason.THREAT_DETECTED,
            duration_override=999,
        )
        assert record.expires_at >= before + 999
        assert record.expires_at <= time.time() + 999 + 1

    def test_isolate_escalates_on_repeated_same_reason(self):
        mgr = self._make_manager()
        # First isolation
        record1 = mgr.isolate("target-1", IsolationReason.THREAT_DETECTED)
        assert record1.escalation_count == 0
        assert record1.level == IsolationLevel.RESTRICTED

        # Second call with same reason should escalate
        record2 = mgr.isolate("target-1", IsolationReason.THREAT_DETECTED)
        assert record2.escalation_count == 1
        # Escalation level 1 for threat_response is QUARANTINE
        assert record2.level == IsolationLevel.QUARANTINE

    def test_isolate_does_not_escalate_on_different_reason(self):
        mgr = self._make_manager()
        mgr.isolate("target-1", IsolationReason.THREAT_DETECTED)
        # Different reason - should replace, not escalate
        record2 = mgr.isolate("target-1", IsolationReason.ANOMALY_DETECTED)
        # New record, not escalated
        assert record2.escalation_count == 0

    def test_isolate_without_policy_uses_defaults(self):
        mgr = self._make_manager()
        # ADMIN_ACTION has no default policy
        record = mgr.isolate("target-1", IsolationReason.ADMIN_ACTION)
        assert record.level == IsolationLevel.RESTRICTED
        assert record.auto_recover is True

    def test_isolate_without_policy_duration_default(self):
        mgr = self._make_manager()
        before = time.time()
        record = mgr.isolate("target-1", IsolationReason.ADMIN_ACTION)
        # Default duration is 300s when no policy
        assert record.expires_at >= before + 300
        assert record.expires_at <= time.time() + 301

    def test_escalation_updates_expires_at(self):
        mgr = self._make_manager()
        record1 = mgr.isolate("target-1", IsolationReason.THREAT_DETECTED)
        old_expires = record1.expires_at
        # Escalate
        record2 = mgr.isolate("target-1", IsolationReason.THREAT_DETECTED)
        # Duration should be longer due to escalation_multiplier
        assert record2.expires_at > old_expires

    def test_escalation_caps_at_max_level(self):
        mgr = self._make_manager()
        # threat_response policy has 3 levels: RESTRICTED, QUARANTINE, BLOCKED
        r1 = mgr.isolate("target-1", IsolationReason.THREAT_DETECTED)
        r2 = mgr.isolate("target-1", IsolationReason.THREAT_DETECTED)
        r3 = mgr.isolate("target-1", IsolationReason.THREAT_DETECTED)
        # Beyond available levels should stay at last
        assert r3.level == IsolationLevel.BLOCKED
        # Even more escalations should still be BLOCKED
        r4 = mgr.isolate("target-1", IsolationReason.THREAT_DETECTED)
        assert r4.level == IsolationLevel.BLOCKED

    # --- release ---

    def test_release_removes_node(self):
        mgr = self._make_manager()
        mgr.isolate("target-1", IsolationReason.THREAT_DETECTED)
        result = mgr.release("target-1")
        assert result is True
        assert "target-1" not in mgr.isolated_nodes

    def test_release_non_existent_returns_false(self):
        mgr = self._make_manager()
        assert mgr.release("nonexistent") is False

    def test_release_auto_recover_false_without_force(self):
        mgr = self._make_manager()
        # protocol_violation has auto_recover=False
        mgr.isolate("target-1", IsolationReason.PROTOCOL_VIOLATION)
        result = mgr.release("target-1", force=False)
        assert result is False
        assert "target-1" in mgr.isolated_nodes

    def test_release_auto_recover_false_with_force(self):
        mgr = self._make_manager()
        mgr.isolate("target-1", IsolationReason.PROTOCOL_VIOLATION)
        result = mgr.release("target-1", force=True)
        assert result is True
        assert "target-1" not in mgr.isolated_nodes

    def test_release_resets_circuit_breaker(self):
        mgr = self._make_manager()
        mgr.isolate("target-1", IsolationReason.THREAT_DETECTED)
        cb = mgr.circuit_breakers["target-1"]
        # Open the circuit breaker
        for _ in range(10):
            cb.record_failure()
        assert cb.state == CircuitBreaker.State.OPEN

        mgr.release("target-1")
        assert cb.state == CircuitBreaker.State.CLOSED

    # --- get_isolation_level ---

    def test_get_isolation_level_none_for_unknown(self):
        mgr = self._make_manager()
        assert mgr.get_isolation_level("unknown") == IsolationLevel.NONE

    def test_get_isolation_level_returns_current_level(self):
        mgr = self._make_manager()
        mgr.isolate("target-1", IsolationReason.THREAT_DETECTED)
        assert mgr.get_isolation_level("target-1") == IsolationLevel.RESTRICTED

    @patch("src.security.auto_isolation.time")
    def test_get_isolation_level_auto_releases_expired(self, mock_time):
        mgr = self._make_manager()
        mock_time.time.return_value = 1000.0
        mgr.isolate("target-1", IsolationReason.THREAT_DETECTED)

        # Fast forward past expiry
        mock_time.time.return_value = 1000.0 + 86400 + 1
        level = mgr.get_isolation_level("target-1")
        assert level == IsolationLevel.NONE
        assert "target-1" not in mgr.isolated_nodes

    @patch("src.security.auto_isolation.time")
    def test_get_isolation_level_does_not_auto_release_non_recoverable(self, mock_time):
        mgr = self._make_manager()
        mock_time.time.return_value = 1000.0
        # protocol_violation has auto_recover=False
        mgr.isolate("target-1", IsolationReason.PROTOCOL_VIOLATION)

        # Fast forward past expiry
        mock_time.time.return_value = 1000.0 + 700000
        level = mgr.get_isolation_level("target-1")
        # Should still be isolated (auto_recover=False, release returns False)
        # PROTOCOL_VIOLATION maps to BLOCKED level
        assert level == IsolationLevel.BLOCKED
        assert "target-1" in mgr.isolated_nodes

    # --- is_allowed ---

    def test_is_allowed_no_isolation(self):
        mgr = self._make_manager()
        allowed, reason = mgr.is_allowed("target-1", "anything")
        assert allowed is True
        assert reason == "OK"

    def test_is_allowed_monitor_level(self):
        mgr = self._make_manager()
        mgr.isolate(
            "target-1",
            IsolationReason.ANOMALY_DETECTED,
            level_override=IsolationLevel.MONITOR,
        )
        allowed, reason = mgr.is_allowed("target-1", "anything")
        assert allowed is True
        assert reason == "Monitored"

    def test_is_allowed_rate_limit_level(self):
        mgr = self._make_manager()
        mgr.isolate(
            "target-1",
            IsolationReason.THREAT_DETECTED,
            level_override=IsolationLevel.RATE_LIMIT,
        )
        allowed, reason = mgr.is_allowed("target-1", "data_transfer")
        assert allowed is True
        assert reason == "Rate limited"

    def test_is_allowed_restricted_essential_allowed(self):
        mgr = self._make_manager()
        mgr.isolate("target-1", IsolationReason.THREAT_DETECTED)
        # RESTRICTED level - essential ops allowed
        for op in ["health", "heartbeat", "auth"]:
            allowed, reason = mgr.is_allowed("target-1", op)
            assert allowed is True, f"Expected {op} to be allowed"
            assert "essential" in reason.lower()

    def test_is_allowed_restricted_non_essential_blocked(self):
        mgr = self._make_manager()
        mgr.isolate("target-1", IsolationReason.THREAT_DETECTED)
        allowed, reason = mgr.is_allowed("target-1", "data_transfer")
        assert allowed is False
        assert "not allowed" in reason.lower()

    def test_is_allowed_quarantine_health_only(self):
        mgr = self._make_manager()
        mgr.isolate(
            "target-1",
            IsolationReason.THREAT_DETECTED,
            level_override=IsolationLevel.QUARANTINE,
        )
        allowed, reason = mgr.is_allowed("target-1", "health")
        assert allowed is True

        allowed, reason = mgr.is_allowed("target-1", "data_transfer")
        assert allowed is False
        assert "quarantine" in reason.lower()

    def test_is_allowed_blocked_denies_everything(self):
        mgr = self._make_manager()
        mgr.isolate(
            "target-1",
            IsolationReason.THREAT_DETECTED,
            level_override=IsolationLevel.BLOCKED,
        )
        for op in ["health", "heartbeat", "auth", "data_transfer", "anything"]:
            allowed, reason = mgr.is_allowed("target-1", op)
            assert allowed is False, f"Expected {op} to be blocked"
            assert reason == "Blocked"

    def test_is_allowed_circuit_breaker_open_blocks(self):
        mgr = self._make_manager()
        cb = mgr.circuit_breakers["target-1"]
        # Open the circuit breaker
        cb.failure_threshold = 1
        cb.record_failure()
        assert cb.state == CircuitBreaker.State.OPEN

        allowed, reason = mgr.is_allowed("target-1", "anything")
        assert allowed is False
        assert "circuit breaker" in reason.lower()

    # --- record_success / record_failure ---

    def test_record_success_delegates_to_circuit_breaker(self):
        mgr = self._make_manager()
        cb = mgr.circuit_breakers["target-1"]
        cb.record_failure()
        cb.record_failure()
        assert cb.failure_count == 2
        mgr.record_success("target-1")
        assert cb.failure_count == 1

    def test_record_failure_delegates_to_circuit_breaker(self):
        mgr = self._make_manager()
        mgr.record_failure("target-1")
        cb = mgr.circuit_breakers["target-1"]
        assert cb.failure_count == 1

    # --- cleanup_expired ---

    @patch("src.security.auto_isolation.time")
    def test_cleanup_expired_removes_expired_auto_recover(self, mock_time):
        mgr = self._make_manager()
        mock_time.time.return_value = 1000.0
        mgr.isolate("node-1", IsolationReason.THREAT_DETECTED)
        mgr.isolate("node-2", IsolationReason.ANOMALY_DETECTED)

        # Fast forward past all durations
        mock_time.time.return_value = 1000.0 + 100000
        count = mgr.cleanup_expired()
        assert count == 2
        assert len(mgr.isolated_nodes) == 0

    @patch("src.security.auto_isolation.time")
    def test_cleanup_expired_keeps_non_auto_recover(self, mock_time):
        mgr = self._make_manager()
        mock_time.time.return_value = 1000.0
        mgr.isolate("node-1", IsolationReason.PROTOCOL_VIOLATION)  # auto_recover=False

        # Fast forward past expiry
        mock_time.time.return_value = 1000.0 + 700000
        count = mgr.cleanup_expired()
        assert count == 0
        assert "node-1" in mgr.isolated_nodes

    @patch("src.security.auto_isolation.time")
    def test_cleanup_expired_keeps_non_expired(self, mock_time):
        mgr = self._make_manager()
        mock_time.time.return_value = 1000.0
        mgr.isolate("node-1", IsolationReason.THREAT_DETECTED)

        # Still within duration
        mock_time.time.return_value = 1001.0
        count = mgr.cleanup_expired()
        assert count == 0
        assert "node-1" in mgr.isolated_nodes

    # --- get_isolated_nodes ---

    def test_get_isolated_nodes_returns_dicts(self):
        mgr = self._make_manager()
        mgr.isolate("node-1", IsolationReason.THREAT_DETECTED)
        mgr.isolate("node-2", IsolationReason.ANOMALY_DETECTED)
        nodes = mgr.get_isolated_nodes()
        assert len(nodes) == 2
        node_ids = {n["node_id"] for n in nodes}
        assert node_ids == {"node-1", "node-2"}

    def test_get_isolated_nodes_empty_initially(self):
        mgr = self._make_manager()
        assert mgr.get_isolated_nodes() == []

    @patch("src.security.auto_isolation.time")
    def test_get_isolated_nodes_excludes_expired(self, mock_time):
        mgr = self._make_manager()
        mock_time.time.return_value = 1000.0
        mgr.isolate("node-1", IsolationReason.THREAT_DETECTED)

        mock_time.time.return_value = 1000.0 + 100000
        nodes = mgr.get_isolated_nodes()
        assert len(nodes) == 0

    # --- get_stats ---

    def test_get_stats_initially_empty(self):
        mgr = self._make_manager()
        stats = mgr.get_stats()
        assert stats["total_isolated"] == 0
        assert stats["by_level"] == {}
        assert stats["by_reason"] == {}
        assert stats["open_circuit_breakers"] == 0

    def test_get_stats_counts_correctly(self):
        mgr = self._make_manager()
        mgr.isolate("node-1", IsolationReason.THREAT_DETECTED)
        mgr.isolate("node-2", IsolationReason.THREAT_DETECTED)
        mgr.isolate("node-3", IsolationReason.ANOMALY_DETECTED)
        stats = mgr.get_stats()
        assert stats["total_isolated"] == 3
        assert stats["by_reason"]["threat_detected"] == 2
        assert stats["by_reason"]["anomaly_detected"] == 1

    def test_get_stats_counts_open_circuit_breakers(self):
        mgr = self._make_manager()
        cb = mgr.circuit_breakers["node-1"]
        cb.failure_threshold = 1
        cb.record_failure()
        assert cb.state == CircuitBreaker.State.OPEN

        stats = mgr.get_stats()
        assert stats["open_circuit_breakers"] == 1
        assert stats["total_circuit_breakers"] == 1

    # --- callbacks ---

    def test_register_and_notify_callback(self):
        mgr = self._make_manager()
        events = []
        mgr.register_callback(lambda nid, lvl: events.append((nid, lvl)))

        mgr.isolate("target-1", IsolationReason.THREAT_DETECTED)
        assert len(events) == 1
        assert events[0] == ("target-1", IsolationLevel.RESTRICTED)

    def test_callback_on_release(self):
        mgr = self._make_manager()
        events = []
        mgr.register_callback(lambda nid, lvl: events.append((nid, lvl)))

        mgr.isolate("target-1", IsolationReason.THREAT_DETECTED)
        mgr.release("target-1")
        # Second event should be NONE (release)
        assert events[-1] == ("target-1", IsolationLevel.NONE)

    def test_callback_exception_does_not_propagate(self):
        mgr = self._make_manager()

        def bad_callback(nid, lvl):
            raise RuntimeError("callback error")

        mgr.register_callback(bad_callback)
        # Should not raise
        record = mgr.isolate("target-1", IsolationReason.THREAT_DETECTED)
        assert record.node_id == "target-1"

    def test_callback_on_escalation(self):
        mgr = self._make_manager()
        events = []
        mgr.register_callback(lambda nid, lvl: events.append((nid, lvl)))

        mgr.isolate("target-1", IsolationReason.THREAT_DETECTED)
        mgr.isolate("target-1", IsolationReason.THREAT_DETECTED)  # escalation
        assert len(events) == 2
        assert events[1] == ("target-1", IsolationLevel.QUARANTINE)

    # --- violation counts ---

    def test_violation_counts_increment(self):
        mgr = self._make_manager()
        mgr.isolate("node-1", IsolationReason.THREAT_DETECTED)
        mgr.isolate("node-1", IsolationReason.THREAT_DETECTED)
        assert mgr.violation_counts["node-1"][IsolationReason.THREAT_DETECTED] == 2

    def test_violation_counts_per_reason(self):
        mgr = self._make_manager()
        mgr.isolate("node-1", IsolationReason.THREAT_DETECTED)
        mgr.isolate("node-1", IsolationReason.ANOMALY_DETECTED)
        assert mgr.violation_counts["node-1"][IsolationReason.THREAT_DETECTED] == 1
        assert mgr.violation_counts["node-1"][IsolationReason.ANOMALY_DETECTED] == 1

    # --- isolate with expired existing record ---

    @patch("src.security.auto_isolation.time")
    def test_isolate_replaces_expired_record(self, mock_time):
        mgr = self._make_manager()
        mock_time.time.return_value = 1000.0
        mgr.isolate("target-1", IsolationReason.THREAT_DETECTED)

        # Fast forward past expiry
        mock_time.time.return_value = 1000.0 + 100000
        # Same reason but expired - should create new, not escalate
        record = mgr.isolate("target-1", IsolationReason.THREAT_DETECTED)
        assert record.escalation_count == 0


# ---------------------------------------------------------------------------
# QuarantineZone
# ---------------------------------------------------------------------------
class TestQuarantineZone:
    """Tests for QuarantineZone."""

    def test_initial_state(self):
        qz = QuarantineZone("zone-1")
        assert qz.zone_id == "zone-1"
        assert len(qz.nodes) == 0
        assert qz.max_bandwidth == 1024
        assert qz.allowed_operations == {"health", "metrics"}

    def test_add_node(self):
        qz = QuarantineZone("zone-1")
        qz.add_node("node-1")
        assert "node-1" in qz.nodes
        assert qz.is_quarantined("node-1")

    def test_add_node_idempotent(self):
        qz = QuarantineZone("zone-1")
        qz.add_node("node-1")
        qz.add_node("node-1")
        assert len(qz.nodes) == 1

    def test_remove_node(self):
        qz = QuarantineZone("zone-1")
        qz.add_node("node-1")
        qz.remove_node("node-1")
        assert not qz.is_quarantined("node-1")

    def test_remove_node_not_present(self):
        qz = QuarantineZone("zone-1")
        # discard does not raise
        qz.remove_node("nonexistent")
        assert len(qz.nodes) == 0

    def test_is_quarantined_true(self):
        qz = QuarantineZone("zone-1")
        qz.add_node("node-1")
        assert qz.is_quarantined("node-1") is True

    def test_is_quarantined_false(self):
        qz = QuarantineZone("zone-1")
        assert qz.is_quarantined("node-1") is False

    # --- can_communicate ---

    def test_can_communicate_neither_quarantined(self):
        qz = QuarantineZone("zone-1")
        assert qz.can_communicate("a", "b") is True

    def test_can_communicate_both_quarantined(self):
        qz = QuarantineZone("zone-1")
        qz.add_node("a")
        qz.add_node("b")
        assert qz.can_communicate("a", "b") is True

    def test_can_communicate_source_quarantined_target_not(self):
        qz = QuarantineZone("zone-1")
        qz.add_node("a")
        assert qz.can_communicate("a", "b") is False

    def test_can_communicate_target_quarantined_source_not(self):
        qz = QuarantineZone("zone-1")
        qz.add_node("b")
        assert qz.can_communicate("a", "b") is False

    def test_can_communicate_allowed_peer_as_target(self):
        qz = QuarantineZone("zone-1")
        qz.add_node("a")
        qz.allowed_peers.add("b")
        # Source quarantined, target is allowed peer
        assert qz.can_communicate("a", "b") is True

    def test_can_communicate_allowed_peer_as_source(self):
        qz = QuarantineZone("zone-1")
        qz.add_node("b")
        qz.allowed_peers.add("a")
        # Target quarantined, source is allowed peer
        assert qz.can_communicate("a", "b") is True

    def test_can_communicate_quarantined_to_non_peer_blocked(self):
        qz = QuarantineZone("zone-1")
        qz.add_node("a")
        qz.allowed_peers.add("c")  # c is allowed, but b is not
        assert qz.can_communicate("a", "b") is False

    # --- is_operation_allowed ---

    def test_is_operation_allowed_default_health(self):
        qz = QuarantineZone("zone-1")
        assert qz.is_operation_allowed("health") is True

    def test_is_operation_allowed_default_metrics(self):
        qz = QuarantineZone("zone-1")
        assert qz.is_operation_allowed("metrics") is True

    def test_is_operation_allowed_denied_by_default(self):
        qz = QuarantineZone("zone-1")
        assert qz.is_operation_allowed("data_transfer") is False
        assert qz.is_operation_allowed("auth") is False

    def test_is_operation_allowed_custom_operations(self):
        qz = QuarantineZone("zone-1")
        qz.allowed_operations.add("debug")
        assert qz.is_operation_allowed("debug") is True

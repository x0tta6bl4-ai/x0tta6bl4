"""Unit tests for quorum_validation module."""

import time
from unittest.mock import patch

import pytest

try:
    from src.network.byzantine.quorum_validation import (CriticalEvent,
                                                         CriticalEventType,
                                                         QuorumValidator)
except ImportError:
    pytest.skip(
        "quorum_validation module not available",
        allow_module_level=True,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def validator():
    """QuorumValidator with 5 nodes and default threshold (0.67)."""
    return QuorumValidator(node_id="node-1", total_nodes=5)


@pytest.fixture
def validator_10():
    """QuorumValidator with 10 nodes and 0.5 threshold."""
    return QuorumValidator(node_id="node-1", total_nodes=10, quorum_threshold=0.5)


@pytest.fixture
def mock_time():
    """Patch time.time() to return a deterministic value."""
    with patch(
        "src.network.byzantine.quorum_validation.time.time", return_value=1700000000.0
    ):
        yield


# ===========================================================================
# TestCriticalEventType
# ===========================================================================


class TestCriticalEventType:
    """Tests for the CriticalEventType enum."""

    def test_all_six_enum_members_exist(self):
        members = [
            CriticalEventType.NODE_FAILURE,
            CriticalEventType.LINK_DOWN,
            CriticalEventType.TOPOLOGY_PARTITION,
            CriticalEventType.GOVERNANCE_PROPOSAL,
            CriticalEventType.KEY_ROTATION,
            CriticalEventType.SECURITY_INCIDENT,
        ]
        assert len(members) == 6
        assert len(CriticalEventType) == 6

    def test_enum_values_are_correct_strings(self):
        assert CriticalEventType.NODE_FAILURE.value == "node_failure"
        assert CriticalEventType.LINK_DOWN.value == "link_down"
        assert CriticalEventType.TOPOLOGY_PARTITION.value == "topology_partition"
        assert CriticalEventType.GOVERNANCE_PROPOSAL.value == "governance_proposal"
        assert CriticalEventType.KEY_ROTATION.value == "key_rotation"
        assert CriticalEventType.SECURITY_INCIDENT.value == "security_incident"


# ===========================================================================
# TestCriticalEvent
# ===========================================================================


class TestCriticalEvent:
    """Tests for the CriticalEvent dataclass."""

    def test_creation_with_all_fields(self):
        sigs = {"v1": b"sig1"}
        event = CriticalEvent(
            event_type=CriticalEventType.NODE_FAILURE,
            source="node-a",
            target="node-b",
            timestamp=1700000000.0,
            evidence={"metric": "cpu_high"},
            signatures=sigs,
            validated=True,
            quorum_reached=True,
        )
        assert event.event_type == CriticalEventType.NODE_FAILURE
        assert event.source == "node-a"
        assert event.target == "node-b"
        assert event.timestamp == 1700000000.0
        assert event.evidence == {"metric": "cpu_high"}
        assert event.signatures == {"v1": b"sig1"}
        assert event.validated is True
        assert event.quorum_reached is True

    def test_default_values(self):
        event = CriticalEvent(
            event_type=CriticalEventType.LINK_DOWN,
            source="node-a",
            target="link-1",
            timestamp=100.0,
            evidence={},
            signatures={},
        )
        assert event.validated is False
        assert event.quorum_reached is False

    def test_add_signature_adds_to_dict(self):
        event = CriticalEvent(
            event_type=CriticalEventType.KEY_ROTATION,
            source="node-a",
            target="node-b",
            timestamp=100.0,
            evidence={},
            signatures={},
        )
        event.add_signature("validator-1", b"sig-abc")
        assert "validator-1" in event.signatures
        assert event.signatures["validator-1"] == b"sig-abc"

    def test_add_signature_overwrites_for_same_node_id(self):
        event = CriticalEvent(
            event_type=CriticalEventType.SECURITY_INCIDENT,
            source="node-a",
            target="node-b",
            timestamp=100.0,
            evidence={},
            signatures={},
        )
        event.add_signature("validator-1", b"first")
        event.add_signature("validator-1", b"second")
        assert len(event.signatures) == 1
        assert event.signatures["validator-1"] == b"second"


# ===========================================================================
# TestQuorumValidatorInit
# ===========================================================================


class TestQuorumValidatorInit:
    """Tests for QuorumValidator.__init__."""

    def test_default_threshold_quorum_size(self):
        # total_nodes=5, threshold=0.67 -> int(5*0.67)+1 = int(3.35)+1 = 3+1 = 4
        qv = QuorumValidator(node_id="n1", total_nodes=5)
        assert qv.node_id == "n1"
        assert qv.total_nodes == 5
        assert pytest.approx(qv.quorum_threshold, abs=1e-9) == 0.67
        assert qv.quorum_size == 4

    def test_custom_threshold(self):
        qv = QuorumValidator(node_id="n1", total_nodes=7, quorum_threshold=0.5)
        # int(7*0.5)+1 = int(3.5)+1 = 3+1 = 4
        assert pytest.approx(qv.quorum_threshold, abs=1e-9) == 0.5
        assert qv.quorum_size == 4

    def test_quorum_size_three_nodes_067(self):
        qv = QuorumValidator(node_id="n1", total_nodes=3, quorum_threshold=0.67)
        # int(3*0.67)+1 = int(2.01)+1 = 2+1 = 3
        assert qv.quorum_size == 3

    def test_quorum_size_ten_nodes_050(self):
        qv = QuorumValidator(node_id="n1", total_nodes=10, quorum_threshold=0.5)
        # int(10*0.5)+1 = int(5.0)+1 = 5+1 = 6
        assert qv.quorum_size == 6


# ===========================================================================
# TestReportCriticalEvent
# ===========================================================================


class TestReportCriticalEvent:
    """Tests for QuorumValidator.report_critical_event."""

    def test_returns_critical_event_with_correct_fields(self, validator, mock_time):
        event = validator.report_critical_event(
            event_type=CriticalEventType.NODE_FAILURE,
            target="node-x",
            evidence={"reason": "heartbeat_timeout"},
        )
        assert isinstance(event, CriticalEvent)
        assert event.event_type == CriticalEventType.NODE_FAILURE
        assert event.target == "node-x"
        assert event.evidence == {"reason": "heartbeat_timeout"}
        assert event.timestamp == 1700000000.0
        assert event.signatures == {}
        assert event.validated is False
        assert event.quorum_reached is False

    def test_uses_self_node_id_as_source_when_none(self, validator, mock_time):
        event = validator.report_critical_event(
            event_type=CriticalEventType.LINK_DOWN,
            target="link-1",
            evidence={},
            source=None,
        )
        assert event.source == "node-1"

    def test_uses_provided_source(self, validator, mock_time):
        event = validator.report_critical_event(
            event_type=CriticalEventType.LINK_DOWN,
            target="link-1",
            evidence={},
            source="node-99",
        )
        assert event.source == "node-99"

    def test_event_stored_in_pending_events(self, validator, mock_time):
        event = validator.report_critical_event(
            event_type=CriticalEventType.TOPOLOGY_PARTITION,
            target="segment-a",
            evidence={"nodes": ["n1", "n2"]},
        )
        # event_id = f"{event_type.value}:{target}:{int(time.time())}"
        expected_id = "topology_partition:segment-a:1700000000"
        assert expected_id in validator._pending_events
        assert validator._pending_events[expected_id] is event


# ===========================================================================
# TestValidateEvent
# ===========================================================================


class TestValidateEvent:
    """Tests for QuorumValidator.validate_event."""

    def test_returns_false_when_quorum_not_reached(self, validator, mock_time):
        # quorum_size = 4 for 5 nodes at 0.67
        event = validator.report_critical_event(
            event_type=CriticalEventType.NODE_FAILURE,
            target="node-x",
            evidence={},
        )
        result = validator.validate_event(event, "v1", b"sig1")
        assert result is False
        assert event.validated is False
        assert event.quorum_reached is False

    def test_returns_true_when_quorum_reached(self, validator, mock_time):
        event = validator.report_critical_event(
            event_type=CriticalEventType.NODE_FAILURE,
            target="node-x",
            evidence={},
        )
        # Need 4 signatures to reach quorum
        validator.validate_event(event, "v1", b"sig1")
        validator.validate_event(event, "v2", b"sig2")
        validator.validate_event(event, "v3", b"sig3")
        result = validator.validate_event(event, "v4", b"sig4")
        assert result is True

    def test_sets_validated_and_quorum_reached_flags(self, validator, mock_time):
        event = validator.report_critical_event(
            event_type=CriticalEventType.SECURITY_INCIDENT,
            target="node-z",
            evidence={"severity": "high"},
        )
        for i in range(1, 5):
            validator.validate_event(event, f"v{i}", f"sig{i}".encode())

        assert event.validated is True
        assert event.quorum_reached is True

    def test_adds_event_id_to_validated_events(self, validator, mock_time):
        event = validator.report_critical_event(
            event_type=CriticalEventType.KEY_ROTATION,
            target="node-y",
            evidence={},
        )
        expected_id = "key_rotation:node-y:1700000000"
        assert expected_id not in validator._validated_events

        for i in range(1, 5):
            validator.validate_event(event, f"v{i}", f"sig{i}".encode())

        assert expected_id in validator._validated_events

    def test_returns_true_immediately_for_already_validated(self, validator, mock_time):
        event = validator.report_critical_event(
            event_type=CriticalEventType.GOVERNANCE_PROPOSAL,
            target="proposal-1",
            evidence={},
        )
        # Reach quorum
        for i in range(1, 5):
            validator.validate_event(event, f"v{i}", f"sig{i}".encode())

        # Now calling again should return True immediately
        # (the event_id is already in _validated_events)
        result = validator.validate_event(event, "v-extra", b"extra-sig")
        assert result is True
        # The extra signature should NOT be added because the method returns
        # before calling add_signature (early return path)
        assert "v-extra" not in event.signatures

    def test_increases_source_reputation_on_quorum_capped_at_1(
        self, validator, mock_time
    ):
        event = validator.report_critical_event(
            event_type=CriticalEventType.NODE_FAILURE,
            target="node-x",
            evidence={},
            source="reporter-a",
        )
        # Default reputation is 1.0, after *1.1 it would be 1.1 but capped at 1.0
        for i in range(1, 5):
            validator.validate_event(event, f"v{i}", f"sig{i}".encode())

        rep = validator.get_source_reputation("reporter-a")
        assert pytest.approx(rep, abs=1e-9) == 1.0


# ===========================================================================
# TestIsValidated
# ===========================================================================


class TestIsValidated:
    """Tests for QuorumValidator.is_validated."""

    def test_returns_false_for_unvalidated_event(self, validator, mock_time):
        event = validator.report_critical_event(
            event_type=CriticalEventType.LINK_DOWN,
            target="link-1",
            evidence={},
        )
        assert validator.is_validated(event) is False

    def test_returns_true_after_quorum_reached(self, validator, mock_time):
        event = validator.report_critical_event(
            event_type=CriticalEventType.LINK_DOWN,
            target="link-1",
            evidence={},
        )
        for i in range(1, 5):
            validator.validate_event(event, f"v{i}", f"sig{i}".encode())

        assert validator.is_validated(event) is True


# ===========================================================================
# TestQuorumProgress
# ===========================================================================


class TestQuorumProgress:
    """Tests for QuorumValidator.get_quorum_progress."""

    def test_returns_current_signatures_and_quorum_size(self, validator, mock_time):
        event = validator.report_critical_event(
            event_type=CriticalEventType.TOPOLOGY_PARTITION,
            target="segment-b",
            evidence={},
        )
        assert validator.get_quorum_progress(event) == (0, 4)

        validator.validate_event(event, "v1", b"sig1")
        assert validator.get_quorum_progress(event) == (1, 4)

        validator.validate_event(event, "v2", b"sig2")
        assert validator.get_quorum_progress(event) == (2, 4)

        validator.validate_event(event, "v3", b"sig3")
        assert validator.get_quorum_progress(event) == (3, 4)

        validator.validate_event(event, "v4", b"sig4")
        assert validator.get_quorum_progress(event) == (4, 4)


# ===========================================================================
# TestReputation
# ===========================================================================


class TestReputation:
    """Tests for reputation-related methods."""

    def test_default_reputation_is_1(self, validator):
        rep = validator.get_source_reputation("unknown-node")
        assert pytest.approx(rep, abs=1e-9) == 1.0

    def test_penalize_source_reduces_by_08(self, validator):
        validator.penalize_source("bad-node", reason="false_report")
        rep = validator.get_source_reputation("bad-node")
        assert pytest.approx(rep, abs=1e-9) == 0.8

    def test_multiple_penalties_stack_multiplicatively(self, validator):
        validator.penalize_source("bad-node", reason="false_report_1")
        validator.penalize_source("bad-node", reason="false_report_2")
        validator.penalize_source("bad-node", reason="false_report_3")
        rep = validator.get_source_reputation("bad-node")
        # 1.0 * 0.8 * 0.8 * 0.8 = 0.512
        assert pytest.approx(rep, abs=1e-6) == 0.512

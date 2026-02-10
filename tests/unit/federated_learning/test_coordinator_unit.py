"""
Unit tests for FederatedCoordinator.

Covers: node management, round lifecycle, model updates, aggregation,
heartbeat monitoring, callbacks, metrics, and edge cases.
"""
import time
import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from src.federated_learning.coordinator import (
    FederatedCoordinator,
    CoordinatorConfig,
    NodeInfo,
    NodeStatus,
    RoundStatus,
    TrainingRound,
)
from src.federated_learning.protocol import (
    ModelUpdate,
    ModelWeights,
    GlobalModel,
    AggregationResult,
)


# --------------- Helpers ---------------

def _make_weights(values=None):
    """Create a simple ModelWeights for testing."""
    values = values or [1.0, 2.0, 3.0]
    return ModelWeights(layer_weights={"flat": values})


def _make_update(node_id, round_number=1, num_samples=100, weights=None, training_time=1.0):
    """Create a ModelUpdate with sensible defaults."""
    return ModelUpdate(
        node_id=node_id,
        round_number=round_number,
        weights=weights or _make_weights(),
        num_samples=num_samples,
        training_time_seconds=training_time,
    )


def _make_coordinator(
    aggregation_method="fedavg",
    min_participants=3,
    target_participants=5,
    **kwargs,
):
    """Build a FederatedCoordinator with test-friendly config."""
    config = CoordinatorConfig(
        aggregation_method=aggregation_method,
        min_participants=min_participants,
        target_participants=target_participants,
        heartbeat_timeout=30.0,
        collection_timeout=60.0,
        **kwargs,
    )
    return FederatedCoordinator("test-coord", config=config)


def _register_nodes(coord, count=5, prefix="node"):
    """Register N online nodes and return their IDs."""
    ids = [f"{prefix}-{i}" for i in range(count)]
    for nid in ids:
        coord.register_node(nid)
    return ids


# --------------- NodeInfo Tests ---------------

class TestNodeInfo:
    """Tests for the NodeInfo dataclass."""

    def test_default_eligible(self):
        node = NodeInfo(node_id="n1", status=NodeStatus.ONLINE)
        assert node.is_eligible()

    def test_idle_is_eligible(self):
        node = NodeInfo(node_id="n1", status=NodeStatus.IDLE)
        assert node.is_eligible()

    def test_stale_not_eligible(self):
        node = NodeInfo(node_id="n1", status=NodeStatus.STALE)
        assert not node.is_eligible()

    def test_banned_not_eligible(self):
        node = NodeInfo(node_id="n1", status=NodeStatus.BANNED)
        assert not node.is_eligible()

    def test_training_not_eligible(self):
        node = NodeInfo(node_id="n1", status=NodeStatus.TRAINING)
        assert not node.is_eligible()

    def test_low_trust_not_eligible(self):
        node = NodeInfo(node_id="n1", status=NodeStatus.ONLINE, trust_score=0.3)
        assert not node.is_eligible(min_trust=0.5)

    def test_three_byzantine_violations_not_eligible(self):
        node = NodeInfo(
            node_id="n1",
            status=NodeStatus.ONLINE,
            byzantine_violations=3,
        )
        assert not node.is_eligible()

    def test_custom_min_trust(self):
        node = NodeInfo(node_id="n1", status=NodeStatus.ONLINE, trust_score=0.6)
        assert node.is_eligible(min_trust=0.5)
        assert not node.is_eligible(min_trust=0.7)


# --------------- TrainingRound Tests ---------------

class TestTrainingRound:
    def test_collection_complete(self):
        r = TrainingRound(round_number=1, min_participants=2)
        r.received_updates = {"a": MagicMock(), "b": MagicMock()}
        assert r.is_collection_complete()

    def test_collection_incomplete(self):
        r = TrainingRound(round_number=1, min_participants=3)
        r.received_updates = {"a": MagicMock()}
        assert not r.is_collection_complete()

    def test_deadline_passed(self):
        r = TrainingRound(round_number=1, collection_deadline=time.time() - 10)
        assert r.is_deadline_passed()

    def test_deadline_not_passed(self):
        r = TrainingRound(round_number=1, collection_deadline=time.time() + 100)
        assert not r.is_deadline_passed()

    def test_to_dict(self):
        r = TrainingRound(round_number=5, status=RoundStatus.STARTED)
        r.selected_nodes = {"n1", "n2"}
        d = r.to_dict()
        assert d["round_number"] == 5
        assert d["status"] == "started"
        assert set(d["selected_nodes"]) == {"n1", "n2"}


# --------------- CoordinatorConfig Tests ---------------

class TestCoordinatorConfig:
    def test_defaults(self):
        cfg = CoordinatorConfig()
        assert cfg.min_participants == 3
        assert cfg.aggregation_method == "krum"
        assert cfg.enable_privacy is True

    def test_custom(self):
        cfg = CoordinatorConfig(min_participants=5, aggregation_method="fedavg")
        assert cfg.min_participants == 5
        assert cfg.aggregation_method == "fedavg"


# --------------- Node Management ---------------

class TestNodeManagement:
    def test_register_node(self):
        coord = _make_coordinator()
        assert coord.register_node("n1") is True
        assert "n1" in coord.nodes
        assert coord.nodes["n1"].status == NodeStatus.ONLINE

    def test_register_node_with_capabilities(self):
        coord = _make_coordinator()
        caps = {"gpu": True, "memory": 8192}
        coord.register_node("n1", capabilities=caps)
        assert coord.nodes["n1"].capabilities == caps

    def test_register_duplicate(self):
        coord = _make_coordinator()
        coord.register_node("n1")
        assert coord.register_node("n1") is False

    def test_unregister_node(self):
        coord = _make_coordinator()
        coord.register_node("n1")
        assert coord.unregister_node("n1") is True
        assert "n1" not in coord.nodes

    def test_unregister_nonexistent(self):
        coord = _make_coordinator()
        assert coord.unregister_node("n1") is False

    def test_ban_node(self):
        coord = _make_coordinator()
        coord.register_node("n1")
        coord.ban_node("n1", "cheating")
        assert coord.nodes["n1"].status == NodeStatus.BANNED
        assert coord.nodes["n1"].byzantine_violations == 1

    def test_ban_nonexistent_no_error(self):
        coord = _make_coordinator()
        coord.ban_node("n1")  # should not raise

    def test_get_eligible_nodes(self):
        coord = _make_coordinator()
        _register_nodes(coord, 3)
        coord.ban_node("node-0")
        eligible = coord.get_eligible_nodes()
        assert "node-0" not in eligible
        assert len(eligible) == 2


# --------------- Heartbeat ---------------

class TestHeartbeat:
    def test_update_heartbeat_resets_missed(self):
        coord = _make_coordinator()
        coord.register_node("n1")
        coord.nodes["n1"].consecutive_missed = 5
        coord.nodes["n1"].status = NodeStatus.STALE
        coord.update_heartbeat("n1")
        assert coord.nodes["n1"].consecutive_missed == 0
        assert coord.nodes["n1"].status == NodeStatus.ONLINE

    def test_update_heartbeat_with_status(self):
        coord = _make_coordinator()
        coord.register_node("n1")
        coord.update_heartbeat("n1", status={"training_loss": 0.42})
        assert coord.nodes["n1"].avg_loss == 0.42

    def test_update_heartbeat_nonexistent(self):
        coord = _make_coordinator()
        coord.update_heartbeat("n1")  # should not raise

    def test_check_heartbeats_marks_stale(self):
        coord = _make_coordinator()
        coord.register_node("n1")
        # Simulate old heartbeat
        coord.nodes["n1"].last_heartbeat = time.time() - 100
        coord.nodes["n1"].consecutive_missed = 2  # needs 3 to go stale
        coord._check_heartbeats()
        assert coord.nodes["n1"].consecutive_missed == 3
        assert coord.nodes["n1"].status == NodeStatus.STALE

    def test_check_heartbeats_skips_banned(self):
        coord = _make_coordinator()
        coord.register_node("n1")
        coord.ban_node("n1")
        coord.nodes["n1"].last_heartbeat = time.time() - 100
        old_missed = coord.nodes["n1"].consecutive_missed
        coord._check_heartbeats()
        # Banned nodes are skipped, missed count should not change
        assert coord.nodes["n1"].consecutive_missed == old_missed

    def test_check_heartbeats_no_stale_if_recent(self):
        coord = _make_coordinator()
        coord.register_node("n1")
        coord._check_heartbeats()
        assert coord.nodes["n1"].status == NodeStatus.ONLINE


# --------------- Round Management ---------------

class TestStartRound:
    def test_start_round_success(self):
        coord = _make_coordinator(min_participants=3, target_participants=5)
        _register_nodes(coord, 5)
        rnd = coord.start_round()
        assert rnd is not None
        assert rnd.status == RoundStatus.STARTED
        assert len(rnd.selected_nodes) <= 5
        assert len(rnd.selected_nodes) >= 1

    def test_start_round_not_enough_nodes(self):
        coord = _make_coordinator(min_participants=3)
        _register_nodes(coord, 2)
        rnd = coord.start_round()
        assert rnd is None

    def test_start_round_while_in_progress(self):
        coord = _make_coordinator(min_participants=3)
        _register_nodes(coord, 5)
        coord.start_round()
        second = coord.start_round()
        assert second is None

    def test_start_round_explicit_number(self):
        coord = _make_coordinator(min_participants=3)
        _register_nodes(coord, 5)
        rnd = coord.start_round(round_number=42)
        assert rnd.round_number == 42

    def test_start_round_auto_increment(self):
        coord = _make_coordinator(min_participants=3)
        _register_nodes(coord, 5)
        rnd1 = coord.start_round()
        assert rnd1.round_number == 1
        # Complete the round and reset node statuses so they're eligible again
        coord.current_round.status = RoundStatus.COMPLETED
        coord.round_history.append(coord.current_round)
        for node in coord.nodes.values():
            node.status = NodeStatus.IDLE
        rnd2 = coord.start_round()
        assert rnd2.round_number == 2

    def test_start_round_sets_node_status_training(self):
        coord = _make_coordinator(min_participants=3)
        _register_nodes(coord, 5)
        rnd = coord.start_round()
        for nid in rnd.selected_nodes:
            assert coord.nodes[nid].status == NodeStatus.TRAINING

    def test_start_round_after_failed_round(self):
        coord = _make_coordinator(min_participants=3)
        _register_nodes(coord, 5)
        rnd1 = coord.start_round()
        rnd1.status = RoundStatus.FAILED
        # Reset node statuses so they're eligible again
        for node in coord.nodes.values():
            node.status = NodeStatus.IDLE
        rnd2 = coord.start_round()
        assert rnd2 is not None


# --------------- Submit Update ---------------

class TestSubmitUpdate:
    def _setup_round(self, coord):
        """Start a round and return selected node IDs."""
        _register_nodes(coord, 5)
        rnd = coord.start_round()
        return list(rnd.selected_nodes)

    def test_submit_update_accepted(self):
        coord = _make_coordinator(min_participants=3)
        selected = self._setup_round(coord)
        update = _make_update(selected[0])
        assert coord.submit_update(update) is True
        assert selected[0] in coord.current_round.received_updates

    def test_submit_update_no_active_round(self):
        coord = _make_coordinator()
        update = _make_update("n1")
        assert coord.submit_update(update) is False

    def test_submit_update_round_not_started(self):
        coord = _make_coordinator(min_participants=3)
        selected = self._setup_round(coord)
        coord.current_round.status = RoundStatus.AGGREGATING
        update = _make_update(selected[0])
        assert coord.submit_update(update) is False

    def test_submit_update_node_not_selected(self):
        coord = _make_coordinator(min_participants=3)
        self._setup_round(coord)
        update = _make_update("not-selected-node")
        assert coord.submit_update(update) is False

    def test_submit_duplicate_update(self):
        coord = _make_coordinator(min_participants=3)
        selected = self._setup_round(coord)
        update = _make_update(selected[0])
        coord.submit_update(update)
        assert coord.submit_update(update) is False

    def test_submit_update_increments_metrics(self):
        coord = _make_coordinator(min_participants=3)
        selected = self._setup_round(coord)
        update = _make_update(selected[0])
        coord.submit_update(update)
        assert coord._metrics["total_updates_received"] == 1

    def test_submit_update_updates_node_stats(self):
        coord = _make_coordinator(min_participants=3)
        selected = self._setup_round(coord)
        update = _make_update(selected[0], num_samples=200, training_time=5.0)
        coord.submit_update(update)
        node = coord.nodes[selected[0]]
        assert node.rounds_participated == 1
        assert node.total_samples_contributed == 200


# --------------- Aggregation Trigger ---------------

class TestAggregation:
    def _fill_round(self, coord, count):
        """Submit `count` updates to the current round from selected nodes."""
        selected = list(coord.current_round.selected_nodes)
        for i in range(min(count, len(selected))):
            update = _make_update(selected[i], num_samples=100)
            coord.submit_update(update)

    def test_auto_aggregate_on_min_participants(self):
        coord = _make_coordinator(
            aggregation_method="fedavg",
            min_participants=3,
            target_participants=5,
        )
        _register_nodes(coord, 5)
        coord.start_round()
        self._fill_round(coord, 3)
        # After meeting min_participants, aggregation triggers
        assert coord.current_round.status in (
            RoundStatus.COMPLETED, RoundStatus.AGGREGATING
        )

    def test_aggregation_success_creates_global_model(self):
        coord = _make_coordinator(
            aggregation_method="fedavg",
            min_participants=3,
            target_participants=5,
        )
        _register_nodes(coord, 5)
        coord.start_round()
        self._fill_round(coord, 3)
        assert coord.global_model is not None
        assert coord._metrics["rounds_completed"] == 1

    def test_aggregation_failure(self):
        coord = _make_coordinator(
            aggregation_method="fedavg",
            min_participants=3,
        )
        _register_nodes(coord, 5)
        coord.start_round()
        # Patch aggregator to fail
        coord.aggregator.aggregate = MagicMock(
            return_value=AggregationResult(
                success=False, error_message="boom"
            )
        )
        self._fill_round(coord, 3)
        assert coord.current_round.status == RoundStatus.FAILED

    def test_aggregation_exception(self):
        coord = _make_coordinator(
            aggregation_method="fedavg",
            min_participants=3,
        )
        _register_nodes(coord, 5)
        coord.start_round()
        coord.aggregator.aggregate = MagicMock(side_effect=RuntimeError("crash"))
        self._fill_round(coord, 3)
        assert coord.current_round.status == RoundStatus.FAILED

    def test_aggregation_resets_node_status(self):
        coord = _make_coordinator(
            aggregation_method="fedavg",
            min_participants=3,
            target_participants=5,
        )
        _register_nodes(coord, 5)
        coord.start_round()
        selected = list(coord.current_round.selected_nodes)
        self._fill_round(coord, 3)
        # After aggregation, selected nodes should be IDLE
        for nid in selected:
            assert coord.nodes[nid].status == NodeStatus.IDLE

    def test_byzantine_detected_lowers_trust(self):
        coord = _make_coordinator(
            aggregation_method="fedavg",
            min_participants=3,
        )
        _register_nodes(coord, 5)
        coord.start_round()
        selected = list(coord.current_round.selected_nodes)

        bad_node = selected[0]
        result = AggregationResult(
            success=True,
            global_model=GlobalModel(
                version=1, round_number=1, weights=_make_weights()
            ),
            suspected_byzantine=[bad_node],
        )
        coord.aggregator.aggregate = MagicMock(return_value=result)
        self._fill_round(coord, 3)
        assert coord.nodes[bad_node].trust_score < 1.0
        assert coord.nodes[bad_node].byzantine_violations >= 1
        assert coord._metrics["byzantine_detections"] >= 1

    def test_byzantine_node_banned_after_three_violations(self):
        coord = _make_coordinator(
            aggregation_method="fedavg",
            min_participants=3,
        )
        _register_nodes(coord, 5)
        # Pre-set violations to 2 so next detection triggers ban
        coord.nodes["node-0"].byzantine_violations = 2
        coord.start_round()
        selected = list(coord.current_round.selected_nodes)
        # Ensure node-0 is in selected (force it)
        if "node-0" not in coord.current_round.selected_nodes:
            coord.current_round.selected_nodes.add("node-0")
            coord.nodes["node-0"].status = NodeStatus.TRAINING

        result = AggregationResult(
            success=True,
            global_model=GlobalModel(
                version=1, round_number=1, weights=_make_weights()
            ),
            suspected_byzantine=["node-0"],
        )
        coord.aggregator.aggregate = MagicMock(return_value=result)
        self._fill_round(coord, 3)
        assert coord.nodes["node-0"].status == NodeStatus.BANNED


# --------------- Round Timeout ---------------

class TestRoundTimeout:
    def test_timeout_no_round(self):
        coord = _make_coordinator()
        assert coord.check_round_timeout() is False

    def test_timeout_round_not_started_status(self):
        coord = _make_coordinator(min_participants=3)
        _register_nodes(coord, 5)
        coord.start_round()
        coord.current_round.status = RoundStatus.AGGREGATING
        assert coord.check_round_timeout() is False

    def test_timeout_with_enough_updates(self):
        coord = _make_coordinator(
            aggregation_method="fedavg",
            min_participants=3,
            target_participants=5,
        )
        _register_nodes(coord, 5)
        coord.start_round()
        # Force deadline in the past
        coord.current_round.collection_deadline = time.time() - 10
        # Submit 2 updates (below min_participants=3, so no auto-aggregation)
        selected = list(coord.current_round.selected_nodes)
        coord.submit_update(_make_update(selected[0]))
        coord.submit_update(_make_update(selected[1]))
        # Now lower min_participants so timeout considers it "enough"
        coord.current_round.min_participants = 2
        result = coord.check_round_timeout()
        assert result is True

    def test_timeout_insufficient_participants_fails(self):
        coord = _make_coordinator(min_participants=3)
        _register_nodes(coord, 5)
        coord.start_round()
        coord.current_round.collection_deadline = time.time() - 10
        # No updates submitted
        result = coord.check_round_timeout()
        assert result is True
        assert coord.current_round.status == RoundStatus.FAILED

    def test_no_timeout_if_deadline_not_passed(self):
        coord = _make_coordinator(min_participants=3)
        _register_nodes(coord, 5)
        coord.start_round()
        coord.current_round.collection_deadline = time.time() + 1000
        assert coord.check_round_timeout() is False


# --------------- Model Management ---------------

class TestModelManagement:
    def test_initialize_model(self):
        coord = _make_coordinator()
        weights = _make_weights([1.0, 2.0])
        model = coord.initialize_model(weights)
        assert model.version == 0
        assert model.round_number == 0
        assert coord.global_model is model

    def test_get_global_model_none(self):
        coord = _make_coordinator()
        assert coord.get_global_model() is None

    def test_get_global_model(self):
        coord = _make_coordinator()
        coord.initialize_model(_make_weights())
        assert coord.get_global_model() is not None


# --------------- Callbacks ---------------

class TestCallbacks:
    def _run_successful_round(self, coord):
        _register_nodes(coord, 5)
        coord.start_round()
        selected = list(coord.current_round.selected_nodes)
        for i in range(3):
            coord.submit_update(_make_update(selected[i]))

    def test_on_round_complete_callback(self):
        coord = _make_coordinator(
            aggregation_method="fedavg", min_participants=3,
        )
        callback = MagicMock()
        coord.on_round_complete(callback)
        self._run_successful_round(coord)
        callback.assert_called_once()

    def test_on_model_update_callback(self):
        coord = _make_coordinator(
            aggregation_method="fedavg", min_participants=3,
        )
        callback = MagicMock()
        coord.on_model_update(callback)
        self._run_successful_round(coord)
        callback.assert_called_once()

    def test_callback_exception_does_not_crash(self):
        coord = _make_coordinator(
            aggregation_method="fedavg", min_participants=3,
        )
        bad_cb = MagicMock(side_effect=ValueError("cb error"))
        coord.on_round_complete(bad_cb)
        # Should not raise
        self._run_successful_round(coord)
        bad_cb.assert_called_once()

    def test_model_update_callback_exception_does_not_crash(self):
        coord = _make_coordinator(
            aggregation_method="fedavg", min_participants=3,
        )
        bad_cb = MagicMock(side_effect=RuntimeError("boom"))
        coord.on_model_update(bad_cb)
        self._run_successful_round(coord)
        bad_cb.assert_called_once()


# --------------- Lifecycle ---------------

class TestLifecycle:
    def test_start_and_stop(self):
        coord = _make_coordinator()
        coord.start()
        assert coord._running is True
        assert coord._heartbeat_thread is not None
        coord.stop()
        assert coord._running is False

    def test_double_start(self):
        coord = _make_coordinator()
        coord.start()
        thread1 = coord._heartbeat_thread
        coord.start()  # Should be a no-op
        assert coord._heartbeat_thread is thread1
        coord.stop()

    def test_stop_without_start(self):
        coord = _make_coordinator()
        coord.stop()  # Should not raise


# --------------- Metrics ---------------

class TestMetrics:
    def test_get_metrics_initial(self):
        coord = _make_coordinator()
        _register_nodes(coord, 3)
        m = coord.get_metrics()
        assert m["registered_nodes"] == 3
        assert m["rounds_completed"] == 0
        assert m["current_round"] is None
        assert m["global_model_version"] == 0

    def test_get_metrics_with_round(self):
        coord = _make_coordinator(min_participants=3)
        _register_nodes(coord, 5)
        coord.start_round()
        m = coord.get_metrics()
        assert m["current_round"] is not None
        assert m["current_round"]["status"] == "started"

    def test_get_metrics_banned_count(self):
        coord = _make_coordinator()
        _register_nodes(coord, 3)
        coord.ban_node("node-0")
        m = coord.get_metrics()
        assert m["banned_nodes"] == 1

    def test_get_node_stats(self):
        coord = _make_coordinator()
        coord.register_node("n1")
        stats = coord.get_node_stats()
        assert "n1" in stats
        assert stats["n1"]["status"] == "online"
        assert stats["n1"]["trust_score"] == 1.0

    def test_get_node_stats_empty(self):
        coord = _make_coordinator()
        assert coord.get_node_stats() == {}


# --------------- Aggregator Initialization ---------------

class TestAggregatorInit:
    def test_krum_aggregator(self):
        coord = _make_coordinator(aggregation_method="krum")
        assert coord.aggregator is not None

    def test_fedavg_aggregator(self):
        coord = _make_coordinator(aggregation_method="fedavg")
        assert coord.aggregator is not None

    def test_default_config(self):
        coord = FederatedCoordinator("c1")
        assert coord.config is not None
        assert coord.aggregator is not None


# --------------- End-to-End Round Flow ---------------

class TestEndToEndRound:
    """Full round lifecycle: register -> start -> submit -> aggregate."""

    def test_full_round_flow(self):
        coord = _make_coordinator(
            aggregation_method="fedavg",
            min_participants=3,
            target_participants=5,
        )
        # Register nodes
        node_ids = _register_nodes(coord, 5)

        # Initialize model
        coord.initialize_model(_make_weights([0.5, 0.5, 0.5]))

        # Start round
        rnd = coord.start_round()
        assert rnd is not None
        assert rnd.round_number == 1

        # Submit updates from all selected nodes
        selected = list(rnd.selected_nodes)
        for i, nid in enumerate(selected):
            w = _make_weights([float(i + 1)] * 3)
            update = _make_update(nid, num_samples=100 * (i + 1), weights=w)
            coord.submit_update(update)

        # Round should be completed
        assert coord.round_history[-1].status == RoundStatus.COMPLETED
        assert coord.global_model is not None
        assert coord.global_model.version >= 1

    def test_two_consecutive_rounds(self):
        coord = _make_coordinator(
            aggregation_method="fedavg",
            min_participants=3,
            target_participants=3,
        )
        _register_nodes(coord, 5)
        coord.initialize_model(_make_weights())

        # Round 1
        rnd1 = coord.start_round()
        for nid in list(rnd1.selected_nodes)[:3]:
            coord.submit_update(_make_update(nid))

        assert coord.round_history[-1].status == RoundStatus.COMPLETED
        v1 = coord.global_model.version

        # Round 2 -- nodes back to IDLE after aggregation
        rnd2 = coord.start_round()
        assert rnd2 is not None
        assert rnd2.round_number == 2
        for nid in list(rnd2.selected_nodes)[:3]:
            coord.submit_update(_make_update(nid, round_number=2))

        assert coord.global_model.version > v1

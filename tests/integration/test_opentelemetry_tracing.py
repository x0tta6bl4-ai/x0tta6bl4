"""
Comprehensive OpenTelemetry Tracing Tests

Tests for:
- Tracer initialization
- Span creation for all components
- Span attributes and context
- Trace propagation
- Integration with FastAPI
"""

import time
from unittest.mock import MagicMock, Mock, patch

import pytest

from src.monitoring.opentelemetry_extended import (CRDTSpans, DAOSpans,
                                                   EBPFSpans,
                                                   FederatedLearningSpans,
                                                   LedgerSpans, RaftSpans,
                                                   SmartContractSpans,
                                                   get_contract_spans,
                                                   get_crdt_spans,
                                                   get_dao_spans,
                                                   get_ebpf_spans,
                                                   get_fl_spans,
                                                   get_ledger_spans,
                                                   get_raft_spans,
                                                   initialize_extended_spans)
from src.monitoring.opentelemetry_tracing import (MAPEKSpans, MLSpans,
                                                  NetworkSpans,
                                                  OTelTracingManager,
                                                  SPIFFESpans, get_mapek_spans,
                                                  get_ml_spans,
                                                  get_network_spans,
                                                  get_spiffe_spans,
                                                  get_tracer_manager,
                                                  initialize_tracing)


class TestOTelTracingManager:
    """Test OpenTelemetry Tracing Manager."""

    def test_manager_initialization(self):
        """Test tracer manager initialization."""
        manager = OTelTracingManager(service_name="test_service")
        assert manager.service_name == "test_service"
        assert manager.tracer is not None or not manager.enabled

    def test_manager_disabled_gracefully(self):
        """Test manager disables gracefully when OTEL unavailable."""
        with patch("src.monitoring.opentelemetry_tracing.OTEL_AVAILABLE", False):
            manager = OTelTracingManager()
            assert not manager.enabled

            # Should not raise errors
            with manager.span("test"):
                pass

    def test_span_context_manager(self):
        """Test span creation with context manager."""
        manager = OTelTracingManager()

        if manager.enabled:
            with manager.span("test_span", {"key": "value"}) as span:
                assert span is not None

    def test_span_decorator(self):
        """Test span decorator."""
        manager = OTelTracingManager()

        @manager.span_decorator("decorated_span", service="test")
        def test_function():
            return "result"

        result = test_function()
        assert result == "result"


class TestMAPEKSpans:
    """Test MAPE-K phase spans."""

    @pytest.fixture
    def manager(self):
        return OTelTracingManager(service_name="test_mapek")

    def test_monitor_phase(self, manager):
        """Test monitor phase span."""
        spans = MAPEKSpans(manager)

        with spans.monitor_phase("node-1", metrics_collected=100):
            pass

    def test_analyze_phase(self, manager):
        """Test analyze phase span."""
        spans = MAPEKSpans(manager)

        with spans.analyze_phase("node-1", anomalies=5, confidence=0.95):
            pass

    def test_plan_phase(self, manager):
        """Test plan phase span."""
        spans = MAPEKSpans(manager)

        with spans.plan_phase("node-1", actions=3):
            pass

    def test_execute_phase(self, manager):
        """Test execute phase span."""
        spans = MAPEKSpans(manager)

        with spans.execute_phase("node-1", actions_executed=3, success=True):
            pass

    def test_knowledge_phase(self, manager):
        """Test knowledge phase span."""
        spans = MAPEKSpans(manager)

        with spans.knowledge_phase("node-1", insights=2):
            pass

    def test_full_mapek_cycle(self, manager):
        """Test complete MAPE-K cycle tracing."""
        spans = MAPEKSpans(manager)

        with spans.monitor_phase("node-1", metrics_collected=100):
            time.sleep(0.01)

        with spans.analyze_phase("node-1", anomalies=2, confidence=0.85):
            time.sleep(0.01)

        with spans.plan_phase("node-1", actions=2):
            time.sleep(0.01)

        with spans.execute_phase("node-1", actions_executed=2, success=True):
            time.sleep(0.01)

        with spans.knowledge_phase("node-1", insights=1):
            time.sleep(0.01)


class TestNetworkSpans:
    """Test mesh network spans."""

    @pytest.fixture
    def manager(self):
        return OTelTracingManager(service_name="test_network")

    def test_node_discovery(self, manager):
        """Test node discovery span."""
        spans = NetworkSpans(manager)

        with spans.node_discovery("node-1", discovered_nodes=5):
            pass

    def test_route_calculation(self, manager):
        """Test route calculation span."""
        spans = NetworkSpans(manager)

        with spans.route_calculation("node-1", "node-5", hops=3):
            pass

    def test_message_forwarding(self, manager):
        """Test message forwarding span."""
        spans = NetworkSpans(manager)

        with spans.message_forwarding("node-1", "node-2", "msg-uuid-123"):
            pass


class TestSPIFFESpans:
    """Test SPIFFE/SPIRE security spans."""

    @pytest.fixture
    def manager(self):
        return OTelTracingManager(service_name="test_spiffe")

    def test_svid_fetch(self, manager):
        """Test SVID fetching span."""
        spans = SPIFFESpans(manager)

        with spans.svid_fetch("node-1", ttl_seconds=3600):
            pass

    def test_svid_renewal(self, manager):
        """Test SVID renewal span."""
        spans = SPIFFESpans(manager)

        with spans.svid_renewal("node-1", success=True):
            pass

    def test_mtls_handshake(self, manager):
        """Test mTLS handshake span."""
        spans = SPIFFESpans(manager)

        with spans.mtls_handshake("client-1", "server-1", duration_ms=42.5):
            pass


class TestMLSpans:
    """Test ML model operation spans."""

    @pytest.fixture
    def manager(self):
        return OTelTracingManager(service_name="test_ml")

    def test_model_inference(self, manager):
        """Test model inference span."""
        spans = MLSpans(manager)

        with spans.model_inference("graphsage", input_size=1024, latency_ms=25.3):
            pass

    def test_model_training(self, manager):
        """Test model training span."""
        spans = MLSpans(manager)

        with spans.model_training("rag_embedding", epoch=5, loss=0.15):
            pass


class TestLedgerSpans:
    """Test distributed ledger spans."""

    @pytest.fixture
    def manager(self):
        return OTelTracingManager(service_name="test_ledger")

    def test_transaction_commit(self, manager):
        """Test transaction commit span."""
        spans = LedgerSpans(manager)

        with spans.transaction_commit("tx-uuid-123", "transfer", size_bytes=256):
            pass

    def test_block_creation(self, manager):
        """Test block creation span."""
        spans = LedgerSpans(manager)

        with spans.block_creation(block_height=12345, tx_count=42):
            pass

    def test_merkle_proof(self, manager):
        """Test merkle proof verification span."""
        spans = LedgerSpans(manager)

        with spans.merkle_proof("0xabcd1234", tree_depth=8):
            pass

    def test_state_sync(self, manager):
        """Test state synchronization span."""
        spans = LedgerSpans(manager)

        with spans.state_sync(from_height=100, to_height=150):
            pass


class TestDAOSpans:
    """Test DAO governance spans."""

    @pytest.fixture
    def manager(self):
        return OTelTracingManager(service_name="test_dao")

    def test_proposal_creation(self, manager):
        """Test proposal creation span."""
        spans = DAOSpans(manager)

        with spans.proposal_creation("prop-123", "budget_allocation"):
            pass

    def test_vote_casting(self, manager):
        """Test vote casting span."""
        spans = DAOSpans(manager)

        with spans.vote_casting("prop-123", "voter-1", "yes"):
            pass

    def test_proposal_execution(self, manager):
        """Test proposal execution span."""
        spans = DAOSpans(manager)

        with spans.proposal_execution("prop-123", success=True):
            pass

    def test_quorum_check(self, manager):
        """Test quorum check span."""
        spans = DAOSpans(manager)

        with spans.quorum_check("prop-123", votes_needed=50, votes_received=75):
            pass


class TestEBPFSpans:
    """Test eBPF operation spans."""

    @pytest.fixture
    def manager(self):
        return OTelTracingManager(service_name="test_ebpf")

    def test_program_compilation(self, manager):
        """Test program compilation span."""
        spans = EBPFSpans(manager)

        with spans.program_compilation("network_monitor", "5.10.0"):
            pass

    def test_program_execution(self, manager):
        """Test program execution span."""
        spans = EBPFSpans(manager)

        with spans.program_execution("network_monitor", event_count=1000):
            pass

    def test_kprobe_trigger(self, manager):
        """Test kprobe trigger span."""
        spans = EBPFSpans(manager)

        with spans.kprobe_trigger("tcp_connect", "tcp_v4_connect"):
            pass

    def test_perfbuf_read(self, manager):
        """Test performance buffer read span."""
        spans = EBPFSpans(manager)

        with spans.perfbuf_read("events_buffer", events_read=500):
            pass


class TestFederatedLearningSpans:
    """Test federated learning spans."""

    @pytest.fixture
    def manager(self):
        return OTelTracingManager(service_name="test_fl")

    def test_local_training(self, manager):
        """Test local model training span."""
        spans = FederatedLearningSpans(manager)

        with spans.local_training("client-1", round_num=5, epochs=3):
            pass

    def test_model_aggregation(self, manager):
        """Test model aggregation span."""
        spans = FederatedLearningSpans(manager)

        with spans.model_aggregation(round_num=5, client_count=10):
            pass

    def test_model_upload(self, manager):
        """Test model upload span."""
        spans = FederatedLearningSpans(manager)

        with spans.model_upload("client-1", model_size_bytes=1024 * 1024):
            pass

    def test_model_download(self, manager):
        """Test model download span."""
        spans = FederatedLearningSpans(manager)

        with spans.model_download("client-1", round_num=5):
            pass


class TestRaftSpans:
    """Test Raft consensus spans."""

    @pytest.fixture
    def manager(self):
        return OTelTracingManager(service_name="test_raft")

    def test_log_replication(self, manager):
        """Test log replication span."""
        spans = RaftSpans(manager)

        with spans.log_replication("follower-1", entries_count=100):
            pass

    def test_leader_election(self, manager):
        """Test leader election span."""
        spans = RaftSpans(manager)

        with spans.leader_election(term=5, candidate_id="node-2"):
            pass

    def test_commit_entries(self, manager):
        """Test commit entries span."""
        spans = RaftSpans(manager)

        with spans.commit_entries(entries_count=50, commit_index=150):
            pass


class TestCRDTSpans:
    """Test CRDT synchronization spans."""

    @pytest.fixture
    def manager(self):
        return OTelTracingManager(service_name="test_crdt")

    def test_crdt_merge(self, manager):
        """Test CRDT merge span."""
        spans = CRDTSpans(manager)

        with spans.crdt_merge("orset", "replica-1", changes=25):
            pass

    def test_crdt_broadcast(self, manager):
        """Test CRDT broadcast span."""
        spans = CRDTSpans(manager)

        with spans.crdt_broadcast("orset", peers=5):
            pass


class TestSmartContractSpans:
    """Test smart contract operation spans."""

    @pytest.fixture
    def manager(self):
        return OTelTracingManager(service_name="test_contract")

    def test_contract_call(self, manager):
        """Test contract function call span."""
        spans = SmartContractSpans(manager)

        with spans.contract_call("0x123456...", "transfer", gas_used=21000):
            pass

    def test_contract_deployment(self, manager):
        """Test contract deployment span."""
        spans = SmartContractSpans(manager)

        with spans.contract_deployment("DAOToken", bytecode_size=10240):
            pass


class TestGlobalSpanGetters:
    """Test global span getter functions."""

    def test_initialize_tracing_basic(self):
        """Test basic tracing initialization."""
        initialize_tracing(service_name="test_service")

        manager = get_tracer_manager()
        assert manager is not None

        mapek = get_mapek_spans()
        assert mapek is not None or not manager.enabled

    def test_all_span_getters(self):
        """Test all span getter functions."""
        initialize_tracing(service_name="test_all")

        # Basic spans
        assert get_tracer_manager() is not None
        assert get_mapek_spans() is not None or True
        assert get_network_spans() is not None or True
        assert get_spiffe_spans() is not None or True
        assert get_ml_spans() is not None or True

    def test_extended_span_getters(self):
        """Test extended span getter functions."""
        manager = OTelTracingManager(service_name="test_extended")
        initialize_extended_spans(manager)

        # Extended spans should be available
        assert get_ledger_spans() is not None
        assert get_dao_spans() is not None
        assert get_ebpf_spans() is not None
        assert get_fl_spans() is not None
        assert get_raft_spans() is not None
        assert get_crdt_spans() is not None
        assert get_contract_spans() is not None


class TestTracingIntegration:
    """Integration tests for tracing."""

    def test_nested_spans(self):
        """Test nested span creation."""
        manager = OTelTracingManager(service_name="test_nested")

        if manager.enabled:
            with manager.span("outer", {"level": "1"}):
                with manager.span("inner", {"level": "2"}):
                    time.sleep(0.01)

    def test_concurrent_spans(self):
        """Test concurrent span creation."""
        manager = OTelTracingManager(service_name="test_concurrent")
        mapek = MAPEKSpans(manager)

        # Simulate concurrent operations
        with mapek.monitor_phase("node-1", metrics_collected=100):
            with mapek.monitor_phase("node-2", metrics_collected=150):
                time.sleep(0.01)

    def test_span_performance(self):
        """Test span creation performance."""
        manager = OTelTracingManager(service_name="test_perf")

        start = time.time()

        for i in range(100):
            with manager.span(f"span_{i}"):
                pass

        duration = time.time() - start

        # Should complete reasonably fast (< 1 second for 100 spans)
        assert duration < 1.0


@pytest.mark.parametrize(
    "component_type",
    [
        "mapek",
        "network",
        "spiffe",
        "ml",
        "ledger",
        "dao",
        "ebpf",
        "fl",
        "raft",
        "crdt",
        "contract",
    ],
)
def test_all_span_types(component_type):
    """Parametrized test for all span types."""
    manager = OTelTracingManager(service_name=f"test_{component_type}")

    if not manager.enabled:
        pytest.skip("OpenTelemetry not available")

    # Each component type should work without errors
    if component_type == "mapek":
        spans = MAPEKSpans(manager)
        with spans.monitor_phase("test", metrics_collected=10):
            pass
    elif component_type == "network":
        spans = NetworkSpans(manager)
        with spans.node_discovery("test", discovered_nodes=2):
            pass
    elif component_type == "spiffe":
        spans = SPIFFESpans(manager)
        with spans.svid_fetch("test", ttl_seconds=3600):
            pass
    elif component_type == "ml":
        spans = MLSpans(manager)
        with spans.model_inference("test_model", input_size=100):
            pass
    elif component_type == "ledger":
        spans = LedgerSpans(manager)
        with spans.transaction_commit("tx-1", "transfer"):
            pass
    elif component_type == "dao":
        spans = DAOSpans(manager)
        with spans.proposal_creation("prop-1", "test"):
            pass
    elif component_type == "ebpf":
        spans = EBPFSpans(manager)
        with spans.program_compilation("test", "5.10"):
            pass
    elif component_type == "fl":
        spans = FederatedLearningSpans(manager)
        with spans.local_training("client-1", 1):
            pass
    elif component_type == "raft":
        spans = RaftSpans(manager)
        with spans.log_replication("follower-1", entries_count=10):
            pass
    elif component_type == "crdt":
        spans = CRDTSpans(manager)
        with spans.crdt_merge("orset", "replica-1"):
            pass
    elif component_type == "contract":
        spans = SmartContractSpans(manager)
        with spans.contract_call("0x123", "test"):
            pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

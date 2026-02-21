import importlib
import os


os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")


class _SpanContext:
    def __init__(self, owner, name, attributes):
        self._owner = owner
        self._name = name
        self._attributes = attributes

    def __enter__(self):
        self._owner.entered.append((self._name, self._attributes))
        return {"name": self._name, "attributes": self._attributes}

    def __exit__(self, exc_type, exc, tb):
        self._owner.exited.append((self._name, exc_type is None))
        return False


class _TracerManager:
    def __init__(self):
        self.calls = []
        self.entered = []
        self.exited = []

    def span(self, name, attributes):
        self.calls.append((name, attributes))
        return _SpanContext(self, name, attributes)


def test_all_extended_span_context_managers():
    mod = importlib.import_module("src.monitoring.opentelemetry_extended")
    tracer = _TracerManager()

    ledger = mod.LedgerSpans(tracer)
    with ledger.transaction_commit("tx-1", "transfer", 128) as span:
        assert span["attributes"]["tx_id"] == "tx-1"
    with ledger.block_creation(42, tx_count=3) as span:
        assert span["attributes"]["block_height"] == 42
    with ledger.merkle_proof("leaf-hash", tree_depth=7) as span:
        assert span["attributes"]["tree_depth"] == 7
    with ledger.state_sync(100, 120) as span:
        assert span["attributes"]["blocks"] == 20

    dao = mod.DAOSpans(tracer)
    with dao.proposal_creation("p-1", "budget") as span:
        assert span["attributes"]["proposal_type"] == "budget"
    with dao.vote_casting("p-1", "alice", "yes") as span:
        assert span["attributes"]["vote_type"] == "yes"
    with dao.proposal_execution("p-1", success=False) as span:
        assert span["attributes"]["success"] is False
    with dao.quorum_check("p-1", votes_needed=10, votes_received=8) as span:
        assert span["attributes"]["votes_needed"] == 10

    ebpf = mod.EBPFSpans(tracer)
    with ebpf.program_compilation("prog", "6.8.0") as span:
        assert span["attributes"]["kernel"] == "6.8.0"
    with ebpf.program_execution("prog", event_count=11) as span:
        assert span["attributes"]["events"] == 11
    with ebpf.kprobe_trigger("kp", "tcp_sendmsg") as span:
        assert span["attributes"]["function"] == "tcp_sendmsg"
    with ebpf.perfbuf_read("buf0", events_read=5) as span:
        assert span["attributes"]["events"] == 5

    fl = mod.FederatedLearningSpans(tracer)
    with fl.local_training("c1", round_num=3, epochs=2) as span:
        assert span["attributes"]["epochs"] == 2
    with fl.model_aggregation(round_num=3, client_count=6) as span:
        assert span["attributes"]["clients"] == 6
    with fl.model_upload("c1", model_size_bytes=2048) as span:
        assert span["attributes"]["size_bytes"] == 2048
    with fl.model_download("c1", round_num=3) as span:
        assert span["attributes"]["round"] == 3

    raft = mod.RaftSpans(tracer)
    with raft.log_replication("follower-1", entries_count=4) as span:
        assert span["attributes"]["entries"] == 4
    with raft.leader_election(term=9, candidate_id="n2") as span:
        assert span["attributes"]["term"] == 9
    with raft.commit_entries(entries_count=4, commit_index=100) as span:
        assert span["attributes"]["commit_index"] == 100

    crdt = mod.CRDTSpans(tracer)
    with crdt.crdt_merge("gset", "r1", changes=2) as span:
        assert span["attributes"]["changes"] == 2
    with crdt.crdt_broadcast("gset", peers=3) as span:
        assert span["attributes"]["peers"] == 3

    contract = mod.SmartContractSpans(tracer)
    with contract.contract_call("0xabc", "transfer", gas_used=9000) as span:
        assert span["attributes"]["gas"] == 9000
    with contract.contract_deployment("Token", bytecode_size=12345) as span:
        assert span["attributes"]["bytecode_size"] == 12345

    expected_span_names = {
        "ledger.transaction_commit",
        "ledger.block_create",
        "ledger.merkle_proof",
        "ledger.state_sync",
        "dao.proposal_create",
        "dao.vote_cast",
        "dao.proposal_execute",
        "dao.quorum_check",
        "ebpf.compile",
        "ebpf.execute",
        "ebpf.kprobe",
        "ebpf.perfbuf_read",
        "fl.local_training",
        "fl.aggregation",
        "fl.model_upload",
        "fl.model_download",
        "raft.log_replicate",
        "raft.leader_election",
        "raft.commit",
        "crdt.merge",
        "crdt.broadcast",
        "contract.call",
        "contract.deploy",
    }
    assert expected_span_names == {name for name, _attrs in tracer.calls}
    assert len(tracer.entered) == len(expected_span_names)
    assert len(tracer.exited) == len(expected_span_names)


def test_initialize_extended_spans_and_getters(monkeypatch):
    mod = importlib.import_module("src.monitoring.opentelemetry_extended")
    tracer = _TracerManager()

    for global_name in (
        "_ledger_spans",
        "_dao_spans",
        "_ebpf_spans",
        "_fl_spans",
        "_raft_spans",
        "_crdt_spans",
        "_contract_spans",
    ):
        monkeypatch.setattr(mod, global_name, None)

    mod.initialize_extended_spans(tracer)

    assert isinstance(mod.get_ledger_spans(), mod.LedgerSpans)
    assert isinstance(mod.get_dao_spans(), mod.DAOSpans)
    assert isinstance(mod.get_ebpf_spans(), mod.EBPFSpans)
    assert isinstance(mod.get_fl_spans(), mod.FederatedLearningSpans)
    assert isinstance(mod.get_raft_spans(), mod.RaftSpans)
    assert isinstance(mod.get_crdt_spans(), mod.CRDTSpans)
    assert isinstance(mod.get_contract_spans(), mod.SmartContractSpans)

    assert mod.get_ledger_spans().tracer is tracer
    assert mod.get_dao_spans().tracer is tracer
    assert mod.get_ebpf_spans().tracer is tracer
    assert mod.get_fl_spans().tracer is tracer
    assert mod.get_raft_spans().tracer is tracer
    assert mod.get_crdt_spans().tracer is tracer
    assert mod.get_contract_spans().tracer is tracer

    assert "initialize_extended_spans" in mod.__all__
    assert "get_ledger_spans" in mod.__all__
    assert "get_contract_spans" in mod.__all__

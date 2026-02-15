"""
Extended OpenTelemetry Tracing with Additional Components

Adds tracing support for:
- Distributed Ledger operations
- DAO Governance voting and proposals
- eBPF program execution
- Federated Learning operations
- Consensus (Raft) operations
- CRDT synchronization
"""

import logging
from contextlib import contextmanager
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class LedgerSpans:
    """Spans for distributed ledger operations."""

    def __init__(self, tracer_manager):
        self.tracer = tracer_manager

    @contextmanager
    def transaction_commit(self, tx_id: str, tx_type: str, size_bytes: int = 0):
        """Span for ledger transaction commit."""
        with self.tracer.span(
            "ledger.transaction_commit",
            {"tx_id": tx_id, "tx_type": tx_type, "size_bytes": size_bytes},
        ) as span:
            yield span

    @contextmanager
    def block_creation(self, block_height: int, tx_count: int = 0):
        """Span for block creation."""
        with self.tracer.span(
            "ledger.block_create", {"block_height": block_height, "tx_count": tx_count}
        ) as span:
            yield span

    @contextmanager
    def merkle_proof(self, leaf_hash: str, tree_depth: int = 0):
        """Span for merkle proof verification."""
        with self.tracer.span(
            "ledger.merkle_proof", {"leaf_hash": leaf_hash, "tree_depth": tree_depth}
        ) as span:
            yield span

    @contextmanager
    def state_sync(self, from_height: int, to_height: int):
        """Span for ledger state synchronization."""
        with self.tracer.span(
            "ledger.state_sync",
            {
                "from_height": from_height,
                "to_height": to_height,
                "blocks": to_height - from_height,
            },
        ) as span:
            yield span


class DAOSpans:
    """Spans for DAO governance operations."""

    def __init__(self, tracer_manager):
        self.tracer = tracer_manager

    @contextmanager
    def proposal_creation(self, proposal_id: str, proposal_type: str):
        """Span for governance proposal creation."""
        with self.tracer.span(
            "dao.proposal_create",
            {"proposal_id": proposal_id, "proposal_type": proposal_type},
        ) as span:
            yield span

    @contextmanager
    def vote_casting(self, proposal_id: str, voter: str, vote_type: str):
        """Span for vote casting."""
        with self.tracer.span(
            "dao.vote_cast",
            {"proposal_id": proposal_id, "voter": voter, "vote_type": vote_type},
        ) as span:
            yield span

    @contextmanager
    def proposal_execution(self, proposal_id: str, success: bool = True):
        """Span for proposal execution."""
        with self.tracer.span(
            "dao.proposal_execute", {"proposal_id": proposal_id, "success": success}
        ) as span:
            yield span

    @contextmanager
    def quorum_check(self, proposal_id: str, votes_needed: int, votes_received: int):
        """Span for quorum checking."""
        with self.tracer.span(
            "dao.quorum_check",
            {
                "proposal_id": proposal_id,
                "votes_needed": votes_needed,
                "votes_received": votes_received,
            },
        ) as span:
            yield span


class EBPFSpans:
    """Spans for eBPF program execution and compilation."""

    def __init__(self, tracer_manager):
        self.tracer = tracer_manager

    @contextmanager
    def program_compilation(self, program_name: str, kernel_version: str):
        """Span for eBPF program compilation."""
        with self.tracer.span(
            "ebpf.compile", {"program": program_name, "kernel": kernel_version}
        ) as span:
            yield span

    @contextmanager
    def program_execution(self, program_name: str, event_count: int = 0):
        """Span for eBPF program execution."""
        with self.tracer.span(
            "ebpf.execute", {"program": program_name, "events": event_count}
        ) as span:
            yield span

    @contextmanager
    def kprobe_trigger(self, probe_name: str, kernel_function: str):
        """Span for kprobe trigger."""
        with self.tracer.span(
            "ebpf.kprobe", {"probe": probe_name, "function": kernel_function}
        ) as span:
            yield span

    @contextmanager
    def perfbuf_read(self, buffer_name: str, events_read: int = 0):
        """Span for performance buffer reading."""
        with self.tracer.span(
            "ebpf.perfbuf_read", {"buffer": buffer_name, "events": events_read}
        ) as span:
            yield span


class FederatedLearningSpans:
    """Spans for federated learning operations."""

    def __init__(self, tracer_manager):
        self.tracer = tracer_manager

    @contextmanager
    def local_training(self, client_id: str, round_num: int, epochs: int = 1):
        """Span for local model training."""
        with self.tracer.span(
            "fl.local_training",
            {"client_id": client_id, "round": round_num, "epochs": epochs},
        ) as span:
            yield span

    @contextmanager
    def model_aggregation(self, round_num: int, client_count: int):
        """Span for federated model aggregation."""
        with self.tracer.span(
            "fl.aggregation", {"round": round_num, "clients": client_count}
        ) as span:
            yield span

    @contextmanager
    def model_upload(self, client_id: str, model_size_bytes: int = 0):
        """Span for uploading local model."""
        with self.tracer.span(
            "fl.model_upload", {"client_id": client_id, "size_bytes": model_size_bytes}
        ) as span:
            yield span

    @contextmanager
    def model_download(self, client_id: str, round_num: int):
        """Span for downloading global model."""
        with self.tracer.span(
            "fl.model_download", {"client_id": client_id, "round": round_num}
        ) as span:
            yield span


class RaftSpans:
    """Spans for Raft consensus operations."""

    def __init__(self, tracer_manager):
        self.tracer = tracer_manager

    @contextmanager
    def log_replication(self, follower_id: str, entries_count: int = 0):
        """Span for log replication."""
        with self.tracer.span(
            "raft.log_replicate", {"follower_id": follower_id, "entries": entries_count}
        ) as span:
            yield span

    @contextmanager
    def leader_election(self, term: int, candidate_id: str):
        """Span for leader election."""
        with self.tracer.span(
            "raft.leader_election", {"term": term, "candidate_id": candidate_id}
        ) as span:
            yield span

    @contextmanager
    def commit_entries(self, entries_count: int, commit_index: int):
        """Span for committing log entries."""
        with self.tracer.span(
            "raft.commit", {"entries": entries_count, "commit_index": commit_index}
        ) as span:
            yield span


class CRDTSpans:
    """Spans for CRDT synchronization operations."""

    def __init__(self, tracer_manager):
        self.tracer = tracer_manager

    @contextmanager
    def crdt_merge(self, crdt_type: str, replica_id: str, changes: int = 0):
        """Span for CRDT merge operation."""
        with self.tracer.span(
            "crdt.merge",
            {"type": crdt_type, "replica_id": replica_id, "changes": changes},
        ) as span:
            yield span

    @contextmanager
    def crdt_broadcast(self, crdt_type: str, peers: int = 0):
        """Span for broadcasting CRDT state."""
        with self.tracer.span(
            "crdt.broadcast", {"type": crdt_type, "peers": peers}
        ) as span:
            yield span


class SmartContractSpans:
    """Spans for smart contract execution."""

    def __init__(self, tracer_manager):
        self.tracer = tracer_manager

    @contextmanager
    def contract_call(
        self, contract_address: str, function_name: str, gas_used: int = 0
    ):
        """Span for smart contract function call."""
        with self.tracer.span(
            "contract.call",
            {"contract": contract_address, "function": function_name, "gas": gas_used},
        ) as span:
            yield span

    @contextmanager
    def contract_deployment(self, contract_name: str, bytecode_size: int = 0):
        """Span for smart contract deployment."""
        with self.tracer.span(
            "contract.deploy",
            {"contract": contract_name, "bytecode_size": bytecode_size},
        ) as span:
            yield span


# Global instances
_ledger_spans = None
_dao_spans = None
_ebpf_spans = None
_fl_spans = None
_raft_spans = None
_crdt_spans = None
_contract_spans = None


def initialize_extended_spans(tracer_manager):
    """Initialize all extended span helpers."""
    global _ledger_spans, _dao_spans, _ebpf_spans, _fl_spans, _raft_spans, _crdt_spans, _contract_spans

    _ledger_spans = LedgerSpans(tracer_manager)
    _dao_spans = DAOSpans(tracer_manager)
    _ebpf_spans = EBPFSpans(tracer_manager)
    _fl_spans = FederatedLearningSpans(tracer_manager)
    _raft_spans = RaftSpans(tracer_manager)
    _crdt_spans = CRDTSpans(tracer_manager)
    _contract_spans = SmartContractSpans(tracer_manager)


def get_ledger_spans() -> Optional[LedgerSpans]:
    """Get ledger spans helper."""
    return _ledger_spans


def get_dao_spans() -> Optional[DAOSpans]:
    """Get DAO spans helper."""
    return _dao_spans


def get_ebpf_spans() -> Optional[EBPFSpans]:
    """Get eBPF spans helper."""
    return _ebpf_spans


def get_fl_spans() -> Optional[FederatedLearningSpans]:
    """Get federated learning spans helper."""
    return _fl_spans


def get_raft_spans() -> Optional[RaftSpans]:
    """Get Raft spans helper."""
    return _raft_spans


def get_crdt_spans() -> Optional[CRDTSpans]:
    """Get CRDT spans helper."""
    return _crdt_spans


def get_contract_spans() -> Optional[SmartContractSpans]:
    """Get smart contract spans helper."""
    return _contract_spans


__all__ = [
    "LedgerSpans",
    "DAOSpans",
    "EBPFSpans",
    "FederatedLearningSpans",
    "RaftSpans",
    "CRDTSpans",
    "SmartContractSpans",
    "initialize_extended_spans",
    "get_ledger_spans",
    "get_dao_spans",
    "get_ebpf_spans",
    "get_fl_spans",
    "get_raft_spans",
    "get_crdt_spans",
    "get_contract_spans",
]

"""
Production-Grade Raft Consensus (P1)
------------------------------------
Implements core Raft responsibilities (Section 5 from Raft paper):
 - Leader election
 - Log replication
 - Safety (term & log consistency checks)
 - Heartbeats
 - Commit & state machine apply callbacks

Supports two modes:
 - Simulation mode (network_client=None): deterministic RPC simulation for tests
 - Network mode (network_client provided): real HTTP RPC via RaftNetworkClient
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class RaftState(Enum):
    FOLLOWER = "follower"
    CANDIDATE = "candidate"
    LEADER = "leader"


@dataclass
class LogEntry:
    term: int
    index: int
    command: Any
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class RaftConfig:
    election_timeout_min: int = 150  # ms
    election_timeout_max: int = 300  # ms
    heartbeat_interval: int = 50  # ms
    rpc_timeout: int = 1000  # ms
    simulate_latency: bool = False


class RaftNode:
    """Single Raft node with optional real network RPC.

    Persistent state (stable storage):
      - current_term
      - voted_for
      - log
    Volatile state (all nodes):
      - commit_index
      - last_applied
    Volatile leader state:
      - next_index
      - match_index
    """

    def __init__(
        self,
        node_id: str,
        peers: List[str],
        config: Optional[RaftConfig] = None,
        rng: Optional[random.Random] = None,
        network_client=None,
        peer_addresses: Optional[Dict[str, str]] = None,
    ):
        self.node_id = node_id
        self.peers = [p for p in peers if p != node_id]
        self.config = config or RaftConfig()
        self.rng = rng or random.Random(42)  # deterministic seed for tests

        # Optional real network layer
        self.network_client = network_client  # RaftNetworkClient or None
        self.peer_addresses = peer_addresses or {}  # {peer_id: "host:port"}

        # Persistent
        self.current_term: int = 0
        self.voted_for: Optional[str] = None
        # Log index starts at 0 with a sentinel entry
        self.log: List[LogEntry] = [LogEntry(term=0, index=0, command=None)]
        
        # Snapshot metadata (persistent)
        self.last_included_index: int = 0
        self.last_included_term: int = 0

        # Volatile
        self.state: RaftState = RaftState.FOLLOWER
        self.commit_index: int = 0
        self.last_applied: int = 0

        # Leader-only (initialized lazily)
        self.next_index: Dict[str, int] = {peer: 1 for peer in self.peers}
        self.match_index: Dict[str, int] = {peer: 0 for peer in self.peers}

        # Timing
        self.election_timeout: int = self._random_timeout()
        self.last_activity: datetime = datetime.now()
        self.last_heartbeat: datetime = datetime.now()

        # Application state machine callbacks
        self.apply_callbacks: List[Callable[[LogEntry], None]] = []

    # ------------------------------------------------------------------
    # Time & Helpers
    # ------------------------------------------------------------------
    def _random_timeout(self) -> int:
        return self.rng.randint(
            self.config.election_timeout_min, self.config.election_timeout_max
        )

    def _reset_election_timer(self):
        self.election_timeout = self._random_timeout()
        self.last_activity = datetime.now()

    # ------------------------------------------------------------------
    # Role Transitions
    # ------------------------------------------------------------------
    def _become_follower(self, term: Optional[int] = None):
        if term is not None and term < self.current_term:
            return
        if term is not None and term > self.current_term:
            self.current_term = term
            self.voted_for = None
        if self.state != RaftState.FOLLOWER:
            logger.info(f"[{self.node_id}] -> FOLLOWER (term={self.current_term})")
        self.state = RaftState.FOLLOWER
        self._reset_election_timer()

    def _become_candidate(self):
        self.state = RaftState.CANDIDATE
        self.current_term += 1
        self.voted_for = self.node_id
        self._reset_election_timer()
        logger.info(f"[{self.node_id}] -> CANDIDATE (term={self.current_term})")

    def _become_leader(self):
        self.state = RaftState.LEADER
        # Initialize leader state
        for peer in self.peers:
            self.next_index[peer] = len(self.log)
            self.match_index[peer] = 0
        logger.info(f"[{self.node_id}] -> LEADER (term={self.current_term})")
        # Immediately send heartbeats
        self._send_heartbeats()

    # ------------------------------------------------------------------
    # Elections
    # ------------------------------------------------------------------
    def _get_last_log_index(self) -> int:
        if self.log:
            return self.log[-1].index
        return self.last_included_index

    def _get_last_log_term(self) -> int:
        if self.log:
            return self.log[-1].term
        return self.last_included_term

    async def start_election_async(self) -> bool:
        """Async election using real network RPC."""
        self._become_candidate()
        votes = 1  # self vote
        last_log_index = self._get_last_log_index()
        last_log_term = self._get_last_log_term()
        for peer in self.peers:
            granted = await self._request_vote_rpc_async(
                peer, self.current_term, last_log_index, last_log_term
            )
            if granted:
                votes += 1
        if votes > len(self.peers) // 2:  # majority
            self._become_leader()
            return True
        return False

    def start_election(self) -> bool:
        """Sync election using simulation (for backward compatibility)."""
        self._become_candidate()
        votes = 1  # self vote
        last_log_index = self._get_last_log_index()
        last_log_term = self._get_last_log_term()
        for peer in self.peers:
            if self._request_vote_rpc_sim(
                peer, self.current_term, last_log_index, last_log_term
            ):
                votes += 1
        if votes > len(self.peers) // 2:  # majority
            self._become_leader()
            return True
        return False

    async def _request_vote_rpc_async(
        self, peer: str, term: int, last_log_index: int, last_log_term: int
    ) -> bool:
        """Send RequestVote RPC — uses real network if available, simulation otherwise."""
        if self.network_client and peer in self.peer_addresses:
            try:
                response = await self.network_client.request_vote(
                    peer_id=peer,
                    peer_address=self.peer_addresses[peer],
                    term=term,
                    candidate_id=self.node_id,
                    last_log_index=last_log_index,
                    last_log_term=last_log_term,
                )
                return response.success
            except Exception as e:
                logger.warning(
                    f"[{self.node_id}] RequestVote RPC to {peer} failed: {e}"
                )
                return False
        return self._request_vote_rpc_sim(peer, term, last_log_index, last_log_term)

    def _request_vote_rpc_sim(
        self, peer: str, term: int, last_log_index: int, last_log_term: int
    ) -> bool:
        """Simulated vote: peer grants with 95% probability for reliable tests."""
        chance = self.rng.random()
        granted = chance < 0.95
        logger.debug(
            f"[{self.node_id}] RequestVote -> {peer} granted={granted} (p={chance:.2f})"
        )
        return granted

    # Backward compat alias
    def _request_vote_rpc(
        self, peer: str, term: int, last_log_index: int, last_log_term: int
    ) -> bool:
        return self._request_vote_rpc_sim(peer, term, last_log_index, last_log_term)

    # ------------------------------------------------------------------
    # Heartbeats & Replication
    # ------------------------------------------------------------------
    def _send_heartbeats(self):
        self.last_heartbeat = datetime.now()
        for peer in self.peers:
            self._append_entries_rpc(peer, heartbeat=True)

    async def _send_heartbeats_async(self):
        self.last_heartbeat = datetime.now()
        for peer in self.peers:
            await self._append_entries_rpc_async(peer, heartbeat=True)

    def append_entry(self, command: Any) -> bool:
        if self.state != RaftState.LEADER:
            logger.warning(f"[{self.node_id}] Reject append: not leader")
            return False
        entry = LogEntry(term=self.current_term, index=self._get_last_log_index() + 1, command=command)
        self.log.append(entry)
        logger.info(
            f"[{self.node_id}] Appended log index={entry.index} term={entry.term}"
        )
        self._replicate()
        return True

    async def append_entry_async(self, command: Any) -> bool:
        """Async version that uses real network for replication."""
        if self.state != RaftState.LEADER:
            logger.warning(f"[{self.node_id}] Reject append: not leader")
            return False
        entry = LogEntry(term=self.current_term, index=self._get_last_log_index() + 1, command=command)
        self.log.append(entry)
        logger.info(
            f"[{self.node_id}] Appended log index={entry.index} term={entry.term}"
        )
        await self._replicate_async()
        return True

    def _replicate(self):
        for peer in self.peers:
            self._append_entries_rpc(peer)
        self._advance_commit_index()

    async def _replicate_async(self):
        for peer in self.peers:
            await self._append_entries_rpc_async(peer)
        self._advance_commit_index()

    async def _append_entries_rpc_async(
        self, peer: str, heartbeat: bool = False
    ) -> bool:
        """Send AppendEntries RPC — uses real network if available."""
        prev_index = self.next_index[peer] - 1
        
        # Correctly calculate prev_term from log or snapshot metadata
        if prev_index == self.last_included_index:
            prev_term = self.last_included_term
        elif prev_index > self.last_included_index:
            log_idx = prev_index - self.last_included_index
            prev_term = self.log[log_idx].term if log_idx < len(self.log) else 0
        else:
            # prev_index is even before snapshot (should trigger InstallSnapshot in real Raft)
            prev_term = 0

        # Calculate entries to send
        log_start_idx = self.next_index[peer] - self.last_included_index
        entries = [] if heartbeat else self.log[max(0, log_start_idx) :]

        if self.network_client and peer in self.peer_addresses:
            try:
                # Serialize entries for transport
                serialized_entries = [
                    {
                        "term": e.term,
                        "index": e.index,
                        "command": e.command,
                        "timestamp": e.timestamp.isoformat(),
                    }
                    for e in entries
                ]
                response = await self.network_client.append_entries(
                    peer_id=peer,
                    peer_address=self.peer_addresses[peer],
                    term=self.current_term,
                    leader_id=self.node_id,
                    prev_log_index=prev_index,
                    prev_log_term=prev_term,
                    entries=serialized_entries,
                    leader_commit=self.commit_index,
                )
                success = response.success
            except Exception as e:
                logger.warning(
                    f"[{self.node_id}] AppendEntries RPC to {peer} failed: {e}"
                )
                success = False
        else:
            success = self._append_entries_rpc_sim(
                peer, heartbeat, prev_index, prev_term, entries
            )

        if success:
            if entries:
                self.match_index[peer] = entries[-1].index
                self.next_index[peer] = self.match_index[peer] + 1
            else:
                self.match_index[peer] = max(self.match_index[peer], prev_index)
        else:
            self.next_index[peer] = max(1, self.next_index[peer] - 1)
        return success

    def _append_entries_rpc(self, peer: str, heartbeat: bool = False) -> bool:
        """Sync simulation AppendEntries (backward compat)."""
        prev_index = self.next_index[peer] - 1
        
        # Correctly calculate prev_term
        if prev_index == self.last_included_index:
            prev_term = self.last_included_term
        elif prev_index > self.last_included_index:
            log_idx = prev_index - self.last_included_index
            prev_term = self.log[log_idx].term if log_idx < len(self.log) else 0
        else:
            prev_term = 0

        log_start_idx = self.next_index[peer] - self.last_included_index
        entries = [] if heartbeat else self.log[max(0, log_start_idx) :]
        success = self._append_entries_rpc_sim(
            peer, heartbeat, prev_index, prev_term, entries
        )
        if success:
            if entries:
                self.match_index[peer] = entries[-1].index
                self.next_index[peer] = self.match_index[peer] + 1
            else:  # heartbeat keeps alignment
                self.match_index[peer] = max(self.match_index[peer], prev_index)
        else:
            # Decrement next_index to retry previous
            self.next_index[peer] = max(1, self.next_index[peer] - 1)
        logger.debug(
            f"[{self.node_id}] AppendEntries -> {peer} success={success} hb={heartbeat} "
            f"prev=({prev_index},{prev_term}) send={len(entries)} next_index={self.next_index[peer]}"
        )
        return success

    def _append_entries_rpc_sim(
        self, peer: str, heartbeat: bool, prev_index: int, prev_term: int, entries: list
    ) -> bool:
        """Simulate success with 80% reliability."""
        return self.rng.random() < 0.8

    def _advance_commit_index(self):
        if self.state != RaftState.LEADER:
            return
        # Find highest N > commit_index such that a majority have match_index >= N and log[N].term == current_term
        last_log_index = self._get_last_log_index()
        for N in range(last_log_index, self.commit_index, -1):
            count = 1  # leader itself
            for peer in self.peers:
                if self.match_index[peer] >= N:
                    count += 1
            
            # Find term of Nth entry
            n_term = 0
            if N == self.last_included_index:
                n_term = self.last_included_term
            elif N > self.last_included_index:
                log_idx = N - self.last_included_index
                if log_idx < len(self.log):
                    n_term = self.log[log_idx].term

            if count > len(self.peers) // 2 and n_term == self.current_term:
                old_commit = self.commit_index
                self.commit_index = N
                logger.debug(
                    f"[{self.node_id}] Commit index advanced {old_commit} -> {self.commit_index}"
                )
                self._apply_entries(old_commit)
                break

    # ------------------------------------------------------------------
    # Apply State Machine
    # ------------------------------------------------------------------
    def _apply_entries(self, from_index: int):
        for i in range(from_index + 1, self.commit_index + 1):
            log_idx = i - self.last_included_index
            if 0 <= log_idx < len(self.log):
                entry = self.log[log_idx]
                self.last_applied = i
                for cb in self.apply_callbacks:
                    try:
                        cb(entry)
                    except Exception as e:  # pragma: no cover - defensive
                        logger.error(f"Apply callback error: {e}")

    def register_apply_callback(self, callback: Callable[[LogEntry], None]):
        self.apply_callbacks.append(callback)

    # ------------------------------------------------------------------
    # RPC Handlers (inbound)
    # ------------------------------------------------------------------
    def receive_append_entries(
        self,
        term: int,
        leader_id: str,
        prev_log_index: int,
        prev_log_term: int,
        entries: List[LogEntry],
        leader_commit: int,
    ) -> bool:
        if term < self.current_term:
            return False
        if term > self.current_term or self.state != RaftState.FOLLOWER:
            self._become_follower(term=term)
        self.last_activity = datetime.now()
        
        # Consistency check
        last_log_index = self._get_last_log_index()
        if prev_log_index > last_log_index:
            return False
        
        # Term check at prev_log_index
        if prev_log_index == self.last_included_index:
            if prev_log_term != self.last_included_term:
                return False
        elif prev_log_index > self.last_included_index:
            log_idx = prev_log_index - self.last_included_index
            if self.log[log_idx].term != prev_log_term:
                return False
        else:
            # prev_log_index is behind our snapshot - old message or needs InstallSnapshot
            return False

        # Append any new entries (overwrite conflicting)
        target_log_idx = prev_log_index - self.last_included_index
        self.log = self.log[: target_log_idx + 1] + entries
        
        if leader_commit > self.commit_index:
            old_commit = self.commit_index
            self.commit_index = min(leader_commit, self._get_last_log_index())
            self._apply_entries(old_commit)
        return True

    def receive_request_vote(
        self, term: int, candidate_id: str, last_log_index: int, last_log_term: int
    ) -> bool:
        if term < self.current_term:
            return False
        if term > self.current_term:
            self._become_follower(term=term)
        # Already voted for someone else
        if self.voted_for is not None and self.voted_for != candidate_id:
            return False
        # Section 5.4.1: candidate's log must be at least as up-to-date
        my_last_index = self._get_last_log_index()
        my_last_term = self._get_last_log_term()
        if last_log_term < my_last_term:
            return False
        if last_log_term == my_last_term and last_log_index < my_last_index:
            return False
        self.voted_for = candidate_id
        self.last_activity = datetime.now()
        return True

    # ------------------------------------------------------------------
    # Timeouts
    # ------------------------------------------------------------------
    def check_timeout(self) -> bool:
        now = datetime.now()
        elapsed_ms = (now - self.last_activity).total_seconds() * 1000
        if self.state == RaftState.LEADER:
            if (
                now - self.last_heartbeat
            ).total_seconds() * 1000 > self.config.heartbeat_interval:
                self._send_heartbeats()
            return False
        else:
            if elapsed_ms > self.election_timeout:
                return self.start_election()
        return False

    async def check_timeout_async(self) -> bool:
        """Async timeout check using real network."""
        now = datetime.now()
        elapsed_ms = (now - self.last_activity).total_seconds() * 1000
        if self.state == RaftState.LEADER:
            if (
                now - self.last_heartbeat
            ).total_seconds() * 1000 > self.config.heartbeat_interval:
                await self._send_heartbeats_async()
            return False
        else:
            if elapsed_ms > self.election_timeout:
                return await self.start_election_async()
        return False

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------
    def get_status(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "state": self.state.value,
            "term": self.current_term,
            "log_length": self._get_last_log_index() + 1,
            "commit_index": self.commit_index,
            "last_applied": self.last_applied,
            "voted_for": self.voted_for,
            "last_included_index": self.last_included_index,
        }


class RaftCluster:
    """Cluster orchestration for in-process tests."""

    def __init__(self, node_ids: List[str], config: Optional[RaftConfig] = None):
        self.config = config or RaftConfig()
        self.nodes: Dict[str, RaftNode] = {
            nid: RaftNode(nid, node_ids, self.config, rng=random.Random(100 + i))
            for i, nid in enumerate(node_ids)
        }

    def get_leader(self) -> Optional[str]:
        for nid, node in self.nodes.items():
            if node.state == RaftState.LEADER:
                return nid
        return None

    def add_command(self, command: Any) -> bool:
        leader_id = self.get_leader()
        if not leader_id:
            return False
        return self.nodes[leader_id].append_entry(command)

    def simulate_tick(self):
        for node in self.nodes.values():
            node.check_timeout()

    def status(self) -> Dict[str, Dict[str, Any]]:
        return {nid: node.get_status() for nid, node in self.nodes.items()}

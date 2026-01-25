"""
Production-Grade Raft Consensus (P1)
------------------------------------
Simplified in-process implementation suitable for unit testing and future
extension with real networking (gRPC / mesh transport).

Implements core Raft responsibilities (§5 from Raft paper):
 - Leader election
 - Log replication
 - Safety (term & log consistency checks)
 - Heartbeats
 - Commit & state machine apply callbacks

NOTE: Networking/RPC layer is simulated. Randomness is bounded to avoid
flaky tests; injection points exist for deterministic strategies.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime, timedelta
from enum import Enum
import random
import logging

logger = logging.getLogger(__name__)
from inspect import signature as _mutmut_signature
from typing import Annotated
from typing import Callable
from typing import ClassVar


MutantDict = Annotated[dict[str, Callable], "Mutant"]


def _mutmut_trampoline(orig, mutants, call_args, call_kwargs, self_arg = None):
    """Forward call to original or mutated function, depending on the environment"""
    import os
    mutant_under_test = os.environ['MUTANT_UNDER_TEST']
    if mutant_under_test == 'fail':
        from mutmut.__main__ import MutmutProgrammaticFailException
        raise MutmutProgrammaticFailException('Failed programmatically')      
    elif mutant_under_test == 'stats':
        from mutmut.__main__ import record_trampoline_hit
        record_trampoline_hit(orig.__module__ + '.' + orig.__name__)
        result = orig(*call_args, **call_kwargs)
        return result
    prefix = orig.__module__ + '.' + orig.__name__ + '__mutmut_'
    if not mutant_under_test.startswith(prefix):
        result = orig(*call_args, **call_kwargs)
        return result
    mutant_name = mutant_under_test.rpartition('.')[-1]
    if self_arg is not None:
        # call to a class method where self is not bound
        result = mutants[mutant_name](self_arg, *call_args, **call_kwargs)
    else:
        result = mutants[mutant_name](*call_args, **call_kwargs)
    return result


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
    election_timeout_min: int = 150   # ms
    election_timeout_max: int = 300   # ms
    heartbeat_interval: int = 50      # ms
    rpc_timeout: int = 1000           # ms
    simulate_latency: bool = False


class RaftNode:
    """Single Raft node with simulated RPC.

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

    def xǁRaftNodeǁ__init____mutmut_orig(self, node_id: str, peers: List[str], config: Optional[RaftConfig] = None,
                 rng: Optional[random.Random] = None):
        self.node_id = node_id
        self.peers = [p for p in peers if p != node_id]
        self.config = config or RaftConfig()
        self.rng = rng or random.Random(42)  # deterministic seed for tests

        # Persistent
        self.current_term: int = 0
        self.voted_for: Optional[str] = None
        # Log index starts at 0 with a sentinel entry
        self.log: List[LogEntry] = [LogEntry(term=0, index=0, command=None)]

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

    def xǁRaftNodeǁ__init____mutmut_1(self, node_id: str, peers: List[str], config: Optional[RaftConfig] = None,
                 rng: Optional[random.Random] = None):
        self.node_id = None
        self.peers = [p for p in peers if p != node_id]
        self.config = config or RaftConfig()
        self.rng = rng or random.Random(42)  # deterministic seed for tests

        # Persistent
        self.current_term: int = 0
        self.voted_for: Optional[str] = None
        # Log index starts at 0 with a sentinel entry
        self.log: List[LogEntry] = [LogEntry(term=0, index=0, command=None)]

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

    def xǁRaftNodeǁ__init____mutmut_2(self, node_id: str, peers: List[str], config: Optional[RaftConfig] = None,
                 rng: Optional[random.Random] = None):
        self.node_id = node_id
        self.peers = None
        self.config = config or RaftConfig()
        self.rng = rng or random.Random(42)  # deterministic seed for tests

        # Persistent
        self.current_term: int = 0
        self.voted_for: Optional[str] = None
        # Log index starts at 0 with a sentinel entry
        self.log: List[LogEntry] = [LogEntry(term=0, index=0, command=None)]

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

    def xǁRaftNodeǁ__init____mutmut_3(self, node_id: str, peers: List[str], config: Optional[RaftConfig] = None,
                 rng: Optional[random.Random] = None):
        self.node_id = node_id
        self.peers = [p for p in peers if p == node_id]
        self.config = config or RaftConfig()
        self.rng = rng or random.Random(42)  # deterministic seed for tests

        # Persistent
        self.current_term: int = 0
        self.voted_for: Optional[str] = None
        # Log index starts at 0 with a sentinel entry
        self.log: List[LogEntry] = [LogEntry(term=0, index=0, command=None)]

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

    def xǁRaftNodeǁ__init____mutmut_4(self, node_id: str, peers: List[str], config: Optional[RaftConfig] = None,
                 rng: Optional[random.Random] = None):
        self.node_id = node_id
        self.peers = [p for p in peers if p != node_id]
        self.config = None
        self.rng = rng or random.Random(42)  # deterministic seed for tests

        # Persistent
        self.current_term: int = 0
        self.voted_for: Optional[str] = None
        # Log index starts at 0 with a sentinel entry
        self.log: List[LogEntry] = [LogEntry(term=0, index=0, command=None)]

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

    def xǁRaftNodeǁ__init____mutmut_5(self, node_id: str, peers: List[str], config: Optional[RaftConfig] = None,
                 rng: Optional[random.Random] = None):
        self.node_id = node_id
        self.peers = [p for p in peers if p != node_id]
        self.config = config and RaftConfig()
        self.rng = rng or random.Random(42)  # deterministic seed for tests

        # Persistent
        self.current_term: int = 0
        self.voted_for: Optional[str] = None
        # Log index starts at 0 with a sentinel entry
        self.log: List[LogEntry] = [LogEntry(term=0, index=0, command=None)]

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

    def xǁRaftNodeǁ__init____mutmut_6(self, node_id: str, peers: List[str], config: Optional[RaftConfig] = None,
                 rng: Optional[random.Random] = None):
        self.node_id = node_id
        self.peers = [p for p in peers if p != node_id]
        self.config = config or RaftConfig()
        self.rng = None  # deterministic seed for tests

        # Persistent
        self.current_term: int = 0
        self.voted_for: Optional[str] = None
        # Log index starts at 0 with a sentinel entry
        self.log: List[LogEntry] = [LogEntry(term=0, index=0, command=None)]

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

    def xǁRaftNodeǁ__init____mutmut_7(self, node_id: str, peers: List[str], config: Optional[RaftConfig] = None,
                 rng: Optional[random.Random] = None):
        self.node_id = node_id
        self.peers = [p for p in peers if p != node_id]
        self.config = config or RaftConfig()
        self.rng = rng and random.Random(42)  # deterministic seed for tests

        # Persistent
        self.current_term: int = 0
        self.voted_for: Optional[str] = None
        # Log index starts at 0 with a sentinel entry
        self.log: List[LogEntry] = [LogEntry(term=0, index=0, command=None)]

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

    def xǁRaftNodeǁ__init____mutmut_8(self, node_id: str, peers: List[str], config: Optional[RaftConfig] = None,
                 rng: Optional[random.Random] = None):
        self.node_id = node_id
        self.peers = [p for p in peers if p != node_id]
        self.config = config or RaftConfig()
        self.rng = rng or random.Random(None)  # deterministic seed for tests

        # Persistent
        self.current_term: int = 0
        self.voted_for: Optional[str] = None
        # Log index starts at 0 with a sentinel entry
        self.log: List[LogEntry] = [LogEntry(term=0, index=0, command=None)]

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

    def xǁRaftNodeǁ__init____mutmut_9(self, node_id: str, peers: List[str], config: Optional[RaftConfig] = None,
                 rng: Optional[random.Random] = None):
        self.node_id = node_id
        self.peers = [p for p in peers if p != node_id]
        self.config = config or RaftConfig()
        self.rng = rng or random.Random(43)  # deterministic seed for tests

        # Persistent
        self.current_term: int = 0
        self.voted_for: Optional[str] = None
        # Log index starts at 0 with a sentinel entry
        self.log: List[LogEntry] = [LogEntry(term=0, index=0, command=None)]

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

    def xǁRaftNodeǁ__init____mutmut_10(self, node_id: str, peers: List[str], config: Optional[RaftConfig] = None,
                 rng: Optional[random.Random] = None):
        self.node_id = node_id
        self.peers = [p for p in peers if p != node_id]
        self.config = config or RaftConfig()
        self.rng = rng or random.Random(42)  # deterministic seed for tests

        # Persistent
        self.current_term: int = None
        self.voted_for: Optional[str] = None
        # Log index starts at 0 with a sentinel entry
        self.log: List[LogEntry] = [LogEntry(term=0, index=0, command=None)]

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

    def xǁRaftNodeǁ__init____mutmut_11(self, node_id: str, peers: List[str], config: Optional[RaftConfig] = None,
                 rng: Optional[random.Random] = None):
        self.node_id = node_id
        self.peers = [p for p in peers if p != node_id]
        self.config = config or RaftConfig()
        self.rng = rng or random.Random(42)  # deterministic seed for tests

        # Persistent
        self.current_term: int = 1
        self.voted_for: Optional[str] = None
        # Log index starts at 0 with a sentinel entry
        self.log: List[LogEntry] = [LogEntry(term=0, index=0, command=None)]

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

    def xǁRaftNodeǁ__init____mutmut_12(self, node_id: str, peers: List[str], config: Optional[RaftConfig] = None,
                 rng: Optional[random.Random] = None):
        self.node_id = node_id
        self.peers = [p for p in peers if p != node_id]
        self.config = config or RaftConfig()
        self.rng = rng or random.Random(42)  # deterministic seed for tests

        # Persistent
        self.current_term: int = 0
        self.voted_for: Optional[str] = ""
        # Log index starts at 0 with a sentinel entry
        self.log: List[LogEntry] = [LogEntry(term=0, index=0, command=None)]

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

    def xǁRaftNodeǁ__init____mutmut_13(self, node_id: str, peers: List[str], config: Optional[RaftConfig] = None,
                 rng: Optional[random.Random] = None):
        self.node_id = node_id
        self.peers = [p for p in peers if p != node_id]
        self.config = config or RaftConfig()
        self.rng = rng or random.Random(42)  # deterministic seed for tests

        # Persistent
        self.current_term: int = 0
        self.voted_for: Optional[str] = None
        # Log index starts at 0 with a sentinel entry
        self.log: List[LogEntry] = None

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

    def xǁRaftNodeǁ__init____mutmut_14(self, node_id: str, peers: List[str], config: Optional[RaftConfig] = None,
                 rng: Optional[random.Random] = None):
        self.node_id = node_id
        self.peers = [p for p in peers if p != node_id]
        self.config = config or RaftConfig()
        self.rng = rng or random.Random(42)  # deterministic seed for tests

        # Persistent
        self.current_term: int = 0
        self.voted_for: Optional[str] = None
        # Log index starts at 0 with a sentinel entry
        self.log: List[LogEntry] = [LogEntry(term=None, index=0, command=None)]

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

    def xǁRaftNodeǁ__init____mutmut_15(self, node_id: str, peers: List[str], config: Optional[RaftConfig] = None,
                 rng: Optional[random.Random] = None):
        self.node_id = node_id
        self.peers = [p for p in peers if p != node_id]
        self.config = config or RaftConfig()
        self.rng = rng or random.Random(42)  # deterministic seed for tests

        # Persistent
        self.current_term: int = 0
        self.voted_for: Optional[str] = None
        # Log index starts at 0 with a sentinel entry
        self.log: List[LogEntry] = [LogEntry(term=0, index=None, command=None)]

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

    def xǁRaftNodeǁ__init____mutmut_16(self, node_id: str, peers: List[str], config: Optional[RaftConfig] = None,
                 rng: Optional[random.Random] = None):
        self.node_id = node_id
        self.peers = [p for p in peers if p != node_id]
        self.config = config or RaftConfig()
        self.rng = rng or random.Random(42)  # deterministic seed for tests

        # Persistent
        self.current_term: int = 0
        self.voted_for: Optional[str] = None
        # Log index starts at 0 with a sentinel entry
        self.log: List[LogEntry] = [LogEntry(index=0, command=None)]

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

    def xǁRaftNodeǁ__init____mutmut_17(self, node_id: str, peers: List[str], config: Optional[RaftConfig] = None,
                 rng: Optional[random.Random] = None):
        self.node_id = node_id
        self.peers = [p for p in peers if p != node_id]
        self.config = config or RaftConfig()
        self.rng = rng or random.Random(42)  # deterministic seed for tests

        # Persistent
        self.current_term: int = 0
        self.voted_for: Optional[str] = None
        # Log index starts at 0 with a sentinel entry
        self.log: List[LogEntry] = [LogEntry(term=0, command=None)]

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

    def xǁRaftNodeǁ__init____mutmut_18(self, node_id: str, peers: List[str], config: Optional[RaftConfig] = None,
                 rng: Optional[random.Random] = None):
        self.node_id = node_id
        self.peers = [p for p in peers if p != node_id]
        self.config = config or RaftConfig()
        self.rng = rng or random.Random(42)  # deterministic seed for tests

        # Persistent
        self.current_term: int = 0
        self.voted_for: Optional[str] = None
        # Log index starts at 0 with a sentinel entry
        self.log: List[LogEntry] = [LogEntry(term=0, index=0, )]

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

    def xǁRaftNodeǁ__init____mutmut_19(self, node_id: str, peers: List[str], config: Optional[RaftConfig] = None,
                 rng: Optional[random.Random] = None):
        self.node_id = node_id
        self.peers = [p for p in peers if p != node_id]
        self.config = config or RaftConfig()
        self.rng = rng or random.Random(42)  # deterministic seed for tests

        # Persistent
        self.current_term: int = 0
        self.voted_for: Optional[str] = None
        # Log index starts at 0 with a sentinel entry
        self.log: List[LogEntry] = [LogEntry(term=1, index=0, command=None)]

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

    def xǁRaftNodeǁ__init____mutmut_20(self, node_id: str, peers: List[str], config: Optional[RaftConfig] = None,
                 rng: Optional[random.Random] = None):
        self.node_id = node_id
        self.peers = [p for p in peers if p != node_id]
        self.config = config or RaftConfig()
        self.rng = rng or random.Random(42)  # deterministic seed for tests

        # Persistent
        self.current_term: int = 0
        self.voted_for: Optional[str] = None
        # Log index starts at 0 with a sentinel entry
        self.log: List[LogEntry] = [LogEntry(term=0, index=1, command=None)]

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

    def xǁRaftNodeǁ__init____mutmut_21(self, node_id: str, peers: List[str], config: Optional[RaftConfig] = None,
                 rng: Optional[random.Random] = None):
        self.node_id = node_id
        self.peers = [p for p in peers if p != node_id]
        self.config = config or RaftConfig()
        self.rng = rng or random.Random(42)  # deterministic seed for tests

        # Persistent
        self.current_term: int = 0
        self.voted_for: Optional[str] = None
        # Log index starts at 0 with a sentinel entry
        self.log: List[LogEntry] = [LogEntry(term=0, index=0, command=None)]

        # Volatile
        self.state: RaftState = None
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

    def xǁRaftNodeǁ__init____mutmut_22(self, node_id: str, peers: List[str], config: Optional[RaftConfig] = None,
                 rng: Optional[random.Random] = None):
        self.node_id = node_id
        self.peers = [p for p in peers if p != node_id]
        self.config = config or RaftConfig()
        self.rng = rng or random.Random(42)  # deterministic seed for tests

        # Persistent
        self.current_term: int = 0
        self.voted_for: Optional[str] = None
        # Log index starts at 0 with a sentinel entry
        self.log: List[LogEntry] = [LogEntry(term=0, index=0, command=None)]

        # Volatile
        self.state: RaftState = RaftState.FOLLOWER
        self.commit_index: int = None
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

    def xǁRaftNodeǁ__init____mutmut_23(self, node_id: str, peers: List[str], config: Optional[RaftConfig] = None,
                 rng: Optional[random.Random] = None):
        self.node_id = node_id
        self.peers = [p for p in peers if p != node_id]
        self.config = config or RaftConfig()
        self.rng = rng or random.Random(42)  # deterministic seed for tests

        # Persistent
        self.current_term: int = 0
        self.voted_for: Optional[str] = None
        # Log index starts at 0 with a sentinel entry
        self.log: List[LogEntry] = [LogEntry(term=0, index=0, command=None)]

        # Volatile
        self.state: RaftState = RaftState.FOLLOWER
        self.commit_index: int = 1
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

    def xǁRaftNodeǁ__init____mutmut_24(self, node_id: str, peers: List[str], config: Optional[RaftConfig] = None,
                 rng: Optional[random.Random] = None):
        self.node_id = node_id
        self.peers = [p for p in peers if p != node_id]
        self.config = config or RaftConfig()
        self.rng = rng or random.Random(42)  # deterministic seed for tests

        # Persistent
        self.current_term: int = 0
        self.voted_for: Optional[str] = None
        # Log index starts at 0 with a sentinel entry
        self.log: List[LogEntry] = [LogEntry(term=0, index=0, command=None)]

        # Volatile
        self.state: RaftState = RaftState.FOLLOWER
        self.commit_index: int = 0
        self.last_applied: int = None

        # Leader-only (initialized lazily)
        self.next_index: Dict[str, int] = {peer: 1 for peer in self.peers}
        self.match_index: Dict[str, int] = {peer: 0 for peer in self.peers}

        # Timing
        self.election_timeout: int = self._random_timeout()
        self.last_activity: datetime = datetime.now()
        self.last_heartbeat: datetime = datetime.now()

        # Application state machine callbacks
        self.apply_callbacks: List[Callable[[LogEntry], None]] = []

    def xǁRaftNodeǁ__init____mutmut_25(self, node_id: str, peers: List[str], config: Optional[RaftConfig] = None,
                 rng: Optional[random.Random] = None):
        self.node_id = node_id
        self.peers = [p for p in peers if p != node_id]
        self.config = config or RaftConfig()
        self.rng = rng or random.Random(42)  # deterministic seed for tests

        # Persistent
        self.current_term: int = 0
        self.voted_for: Optional[str] = None
        # Log index starts at 0 with a sentinel entry
        self.log: List[LogEntry] = [LogEntry(term=0, index=0, command=None)]

        # Volatile
        self.state: RaftState = RaftState.FOLLOWER
        self.commit_index: int = 0
        self.last_applied: int = 1

        # Leader-only (initialized lazily)
        self.next_index: Dict[str, int] = {peer: 1 for peer in self.peers}
        self.match_index: Dict[str, int] = {peer: 0 for peer in self.peers}

        # Timing
        self.election_timeout: int = self._random_timeout()
        self.last_activity: datetime = datetime.now()
        self.last_heartbeat: datetime = datetime.now()

        # Application state machine callbacks
        self.apply_callbacks: List[Callable[[LogEntry], None]] = []

    def xǁRaftNodeǁ__init____mutmut_26(self, node_id: str, peers: List[str], config: Optional[RaftConfig] = None,
                 rng: Optional[random.Random] = None):
        self.node_id = node_id
        self.peers = [p for p in peers if p != node_id]
        self.config = config or RaftConfig()
        self.rng = rng or random.Random(42)  # deterministic seed for tests

        # Persistent
        self.current_term: int = 0
        self.voted_for: Optional[str] = None
        # Log index starts at 0 with a sentinel entry
        self.log: List[LogEntry] = [LogEntry(term=0, index=0, command=None)]

        # Volatile
        self.state: RaftState = RaftState.FOLLOWER
        self.commit_index: int = 0
        self.last_applied: int = 0

        # Leader-only (initialized lazily)
        self.next_index: Dict[str, int] = None
        self.match_index: Dict[str, int] = {peer: 0 for peer in self.peers}

        # Timing
        self.election_timeout: int = self._random_timeout()
        self.last_activity: datetime = datetime.now()
        self.last_heartbeat: datetime = datetime.now()

        # Application state machine callbacks
        self.apply_callbacks: List[Callable[[LogEntry], None]] = []

    def xǁRaftNodeǁ__init____mutmut_27(self, node_id: str, peers: List[str], config: Optional[RaftConfig] = None,
                 rng: Optional[random.Random] = None):
        self.node_id = node_id
        self.peers = [p for p in peers if p != node_id]
        self.config = config or RaftConfig()
        self.rng = rng or random.Random(42)  # deterministic seed for tests

        # Persistent
        self.current_term: int = 0
        self.voted_for: Optional[str] = None
        # Log index starts at 0 with a sentinel entry
        self.log: List[LogEntry] = [LogEntry(term=0, index=0, command=None)]

        # Volatile
        self.state: RaftState = RaftState.FOLLOWER
        self.commit_index: int = 0
        self.last_applied: int = 0

        # Leader-only (initialized lazily)
        self.next_index: Dict[str, int] = {peer: 2 for peer in self.peers}
        self.match_index: Dict[str, int] = {peer: 0 for peer in self.peers}

        # Timing
        self.election_timeout: int = self._random_timeout()
        self.last_activity: datetime = datetime.now()
        self.last_heartbeat: datetime = datetime.now()

        # Application state machine callbacks
        self.apply_callbacks: List[Callable[[LogEntry], None]] = []

    def xǁRaftNodeǁ__init____mutmut_28(self, node_id: str, peers: List[str], config: Optional[RaftConfig] = None,
                 rng: Optional[random.Random] = None):
        self.node_id = node_id
        self.peers = [p for p in peers if p != node_id]
        self.config = config or RaftConfig()
        self.rng = rng or random.Random(42)  # deterministic seed for tests

        # Persistent
        self.current_term: int = 0
        self.voted_for: Optional[str] = None
        # Log index starts at 0 with a sentinel entry
        self.log: List[LogEntry] = [LogEntry(term=0, index=0, command=None)]

        # Volatile
        self.state: RaftState = RaftState.FOLLOWER
        self.commit_index: int = 0
        self.last_applied: int = 0

        # Leader-only (initialized lazily)
        self.next_index: Dict[str, int] = {peer: 1 for peer in self.peers}
        self.match_index: Dict[str, int] = None

        # Timing
        self.election_timeout: int = self._random_timeout()
        self.last_activity: datetime = datetime.now()
        self.last_heartbeat: datetime = datetime.now()

        # Application state machine callbacks
        self.apply_callbacks: List[Callable[[LogEntry], None]] = []

    def xǁRaftNodeǁ__init____mutmut_29(self, node_id: str, peers: List[str], config: Optional[RaftConfig] = None,
                 rng: Optional[random.Random] = None):
        self.node_id = node_id
        self.peers = [p for p in peers if p != node_id]
        self.config = config or RaftConfig()
        self.rng = rng or random.Random(42)  # deterministic seed for tests

        # Persistent
        self.current_term: int = 0
        self.voted_for: Optional[str] = None
        # Log index starts at 0 with a sentinel entry
        self.log: List[LogEntry] = [LogEntry(term=0, index=0, command=None)]

        # Volatile
        self.state: RaftState = RaftState.FOLLOWER
        self.commit_index: int = 0
        self.last_applied: int = 0

        # Leader-only (initialized lazily)
        self.next_index: Dict[str, int] = {peer: 1 for peer in self.peers}
        self.match_index: Dict[str, int] = {peer: 1 for peer in self.peers}

        # Timing
        self.election_timeout: int = self._random_timeout()
        self.last_activity: datetime = datetime.now()
        self.last_heartbeat: datetime = datetime.now()

        # Application state machine callbacks
        self.apply_callbacks: List[Callable[[LogEntry], None]] = []

    def xǁRaftNodeǁ__init____mutmut_30(self, node_id: str, peers: List[str], config: Optional[RaftConfig] = None,
                 rng: Optional[random.Random] = None):
        self.node_id = node_id
        self.peers = [p for p in peers if p != node_id]
        self.config = config or RaftConfig()
        self.rng = rng or random.Random(42)  # deterministic seed for tests

        # Persistent
        self.current_term: int = 0
        self.voted_for: Optional[str] = None
        # Log index starts at 0 with a sentinel entry
        self.log: List[LogEntry] = [LogEntry(term=0, index=0, command=None)]

        # Volatile
        self.state: RaftState = RaftState.FOLLOWER
        self.commit_index: int = 0
        self.last_applied: int = 0

        # Leader-only (initialized lazily)
        self.next_index: Dict[str, int] = {peer: 1 for peer in self.peers}
        self.match_index: Dict[str, int] = {peer: 0 for peer in self.peers}

        # Timing
        self.election_timeout: int = None
        self.last_activity: datetime = datetime.now()
        self.last_heartbeat: datetime = datetime.now()

        # Application state machine callbacks
        self.apply_callbacks: List[Callable[[LogEntry], None]] = []

    def xǁRaftNodeǁ__init____mutmut_31(self, node_id: str, peers: List[str], config: Optional[RaftConfig] = None,
                 rng: Optional[random.Random] = None):
        self.node_id = node_id
        self.peers = [p for p in peers if p != node_id]
        self.config = config or RaftConfig()
        self.rng = rng or random.Random(42)  # deterministic seed for tests

        # Persistent
        self.current_term: int = 0
        self.voted_for: Optional[str] = None
        # Log index starts at 0 with a sentinel entry
        self.log: List[LogEntry] = [LogEntry(term=0, index=0, command=None)]

        # Volatile
        self.state: RaftState = RaftState.FOLLOWER
        self.commit_index: int = 0
        self.last_applied: int = 0

        # Leader-only (initialized lazily)
        self.next_index: Dict[str, int] = {peer: 1 for peer in self.peers}
        self.match_index: Dict[str, int] = {peer: 0 for peer in self.peers}

        # Timing
        self.election_timeout: int = self._random_timeout()
        self.last_activity: datetime = None
        self.last_heartbeat: datetime = datetime.now()

        # Application state machine callbacks
        self.apply_callbacks: List[Callable[[LogEntry], None]] = []

    def xǁRaftNodeǁ__init____mutmut_32(self, node_id: str, peers: List[str], config: Optional[RaftConfig] = None,
                 rng: Optional[random.Random] = None):
        self.node_id = node_id
        self.peers = [p for p in peers if p != node_id]
        self.config = config or RaftConfig()
        self.rng = rng or random.Random(42)  # deterministic seed for tests

        # Persistent
        self.current_term: int = 0
        self.voted_for: Optional[str] = None
        # Log index starts at 0 with a sentinel entry
        self.log: List[LogEntry] = [LogEntry(term=0, index=0, command=None)]

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
        self.last_heartbeat: datetime = None

        # Application state machine callbacks
        self.apply_callbacks: List[Callable[[LogEntry], None]] = []

    def xǁRaftNodeǁ__init____mutmut_33(self, node_id: str, peers: List[str], config: Optional[RaftConfig] = None,
                 rng: Optional[random.Random] = None):
        self.node_id = node_id
        self.peers = [p for p in peers if p != node_id]
        self.config = config or RaftConfig()
        self.rng = rng or random.Random(42)  # deterministic seed for tests

        # Persistent
        self.current_term: int = 0
        self.voted_for: Optional[str] = None
        # Log index starts at 0 with a sentinel entry
        self.log: List[LogEntry] = [LogEntry(term=0, index=0, command=None)]

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
        self.apply_callbacks: List[Callable[[LogEntry], None]] = None
    
    xǁRaftNodeǁ__init____mutmut_mutants : ClassVar[MutantDict] = {
    'xǁRaftNodeǁ__init____mutmut_1': xǁRaftNodeǁ__init____mutmut_1, 
        'xǁRaftNodeǁ__init____mutmut_2': xǁRaftNodeǁ__init____mutmut_2, 
        'xǁRaftNodeǁ__init____mutmut_3': xǁRaftNodeǁ__init____mutmut_3, 
        'xǁRaftNodeǁ__init____mutmut_4': xǁRaftNodeǁ__init____mutmut_4, 
        'xǁRaftNodeǁ__init____mutmut_5': xǁRaftNodeǁ__init____mutmut_5, 
        'xǁRaftNodeǁ__init____mutmut_6': xǁRaftNodeǁ__init____mutmut_6, 
        'xǁRaftNodeǁ__init____mutmut_7': xǁRaftNodeǁ__init____mutmut_7, 
        'xǁRaftNodeǁ__init____mutmut_8': xǁRaftNodeǁ__init____mutmut_8, 
        'xǁRaftNodeǁ__init____mutmut_9': xǁRaftNodeǁ__init____mutmut_9, 
        'xǁRaftNodeǁ__init____mutmut_10': xǁRaftNodeǁ__init____mutmut_10, 
        'xǁRaftNodeǁ__init____mutmut_11': xǁRaftNodeǁ__init____mutmut_11, 
        'xǁRaftNodeǁ__init____mutmut_12': xǁRaftNodeǁ__init____mutmut_12, 
        'xǁRaftNodeǁ__init____mutmut_13': xǁRaftNodeǁ__init____mutmut_13, 
        'xǁRaftNodeǁ__init____mutmut_14': xǁRaftNodeǁ__init____mutmut_14, 
        'xǁRaftNodeǁ__init____mutmut_15': xǁRaftNodeǁ__init____mutmut_15, 
        'xǁRaftNodeǁ__init____mutmut_16': xǁRaftNodeǁ__init____mutmut_16, 
        'xǁRaftNodeǁ__init____mutmut_17': xǁRaftNodeǁ__init____mutmut_17, 
        'xǁRaftNodeǁ__init____mutmut_18': xǁRaftNodeǁ__init____mutmut_18, 
        'xǁRaftNodeǁ__init____mutmut_19': xǁRaftNodeǁ__init____mutmut_19, 
        'xǁRaftNodeǁ__init____mutmut_20': xǁRaftNodeǁ__init____mutmut_20, 
        'xǁRaftNodeǁ__init____mutmut_21': xǁRaftNodeǁ__init____mutmut_21, 
        'xǁRaftNodeǁ__init____mutmut_22': xǁRaftNodeǁ__init____mutmut_22, 
        'xǁRaftNodeǁ__init____mutmut_23': xǁRaftNodeǁ__init____mutmut_23, 
        'xǁRaftNodeǁ__init____mutmut_24': xǁRaftNodeǁ__init____mutmut_24, 
        'xǁRaftNodeǁ__init____mutmut_25': xǁRaftNodeǁ__init____mutmut_25, 
        'xǁRaftNodeǁ__init____mutmut_26': xǁRaftNodeǁ__init____mutmut_26, 
        'xǁRaftNodeǁ__init____mutmut_27': xǁRaftNodeǁ__init____mutmut_27, 
        'xǁRaftNodeǁ__init____mutmut_28': xǁRaftNodeǁ__init____mutmut_28, 
        'xǁRaftNodeǁ__init____mutmut_29': xǁRaftNodeǁ__init____mutmut_29, 
        'xǁRaftNodeǁ__init____mutmut_30': xǁRaftNodeǁ__init____mutmut_30, 
        'xǁRaftNodeǁ__init____mutmut_31': xǁRaftNodeǁ__init____mutmut_31, 
        'xǁRaftNodeǁ__init____mutmut_32': xǁRaftNodeǁ__init____mutmut_32, 
        'xǁRaftNodeǁ__init____mutmut_33': xǁRaftNodeǁ__init____mutmut_33
    }
    
    def __init__(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁRaftNodeǁ__init____mutmut_orig"), object.__getattribute__(self, "xǁRaftNodeǁ__init____mutmut_mutants"), args, kwargs, self)
        return result 
    
    __init__.__signature__ = _mutmut_signature(xǁRaftNodeǁ__init____mutmut_orig)
    xǁRaftNodeǁ__init____mutmut_orig.__name__ = 'xǁRaftNodeǁ__init__'

    # ------------------------------------------------------------------
    # Time & Helpers
    # ------------------------------------------------------------------
    def xǁRaftNodeǁ_random_timeout__mutmut_orig(self) -> int:
        return self.rng.randint(self.config.election_timeout_min, self.config.election_timeout_max)

    # ------------------------------------------------------------------
    # Time & Helpers
    # ------------------------------------------------------------------
    def xǁRaftNodeǁ_random_timeout__mutmut_1(self) -> int:
        return self.rng.randint(None, self.config.election_timeout_max)

    # ------------------------------------------------------------------
    # Time & Helpers
    # ------------------------------------------------------------------
    def xǁRaftNodeǁ_random_timeout__mutmut_2(self) -> int:
        return self.rng.randint(self.config.election_timeout_min, None)

    # ------------------------------------------------------------------
    # Time & Helpers
    # ------------------------------------------------------------------
    def xǁRaftNodeǁ_random_timeout__mutmut_3(self) -> int:
        return self.rng.randint(self.config.election_timeout_max)

    # ------------------------------------------------------------------
    # Time & Helpers
    # ------------------------------------------------------------------
    def xǁRaftNodeǁ_random_timeout__mutmut_4(self) -> int:
        return self.rng.randint(self.config.election_timeout_min, )
    
    xǁRaftNodeǁ_random_timeout__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁRaftNodeǁ_random_timeout__mutmut_1': xǁRaftNodeǁ_random_timeout__mutmut_1, 
        'xǁRaftNodeǁ_random_timeout__mutmut_2': xǁRaftNodeǁ_random_timeout__mutmut_2, 
        'xǁRaftNodeǁ_random_timeout__mutmut_3': xǁRaftNodeǁ_random_timeout__mutmut_3, 
        'xǁRaftNodeǁ_random_timeout__mutmut_4': xǁRaftNodeǁ_random_timeout__mutmut_4
    }
    
    def _random_timeout(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁRaftNodeǁ_random_timeout__mutmut_orig"), object.__getattribute__(self, "xǁRaftNodeǁ_random_timeout__mutmut_mutants"), args, kwargs, self)
        return result 
    
    _random_timeout.__signature__ = _mutmut_signature(xǁRaftNodeǁ_random_timeout__mutmut_orig)
    xǁRaftNodeǁ_random_timeout__mutmut_orig.__name__ = 'xǁRaftNodeǁ_random_timeout'

    def xǁRaftNodeǁ_reset_election_timer__mutmut_orig(self):
        self.election_timeout = self._random_timeout()
        self.last_activity = datetime.now()

    def xǁRaftNodeǁ_reset_election_timer__mutmut_1(self):
        self.election_timeout = None
        self.last_activity = datetime.now()

    def xǁRaftNodeǁ_reset_election_timer__mutmut_2(self):
        self.election_timeout = self._random_timeout()
        self.last_activity = None
    
    xǁRaftNodeǁ_reset_election_timer__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁRaftNodeǁ_reset_election_timer__mutmut_1': xǁRaftNodeǁ_reset_election_timer__mutmut_1, 
        'xǁRaftNodeǁ_reset_election_timer__mutmut_2': xǁRaftNodeǁ_reset_election_timer__mutmut_2
    }
    
    def _reset_election_timer(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁRaftNodeǁ_reset_election_timer__mutmut_orig"), object.__getattribute__(self, "xǁRaftNodeǁ_reset_election_timer__mutmut_mutants"), args, kwargs, self)
        return result 
    
    _reset_election_timer.__signature__ = _mutmut_signature(xǁRaftNodeǁ_reset_election_timer__mutmut_orig)
    xǁRaftNodeǁ_reset_election_timer__mutmut_orig.__name__ = 'xǁRaftNodeǁ_reset_election_timer'

    # ------------------------------------------------------------------
    # Role Transitions
    # ------------------------------------------------------------------
    def xǁRaftNodeǁ_become_follower__mutmut_orig(self, term: Optional[int] = None):
        if term is not None and term < self.current_term:
            return
        if term is not None and term > self.current_term:
            self.current_term = term
            self.voted_for = None
        if self.state != RaftState.FOLLOWER:
            logger.info(f"[{self.node_id}] -> FOLLOWER (term={self.current_term})")
        self.state = RaftState.FOLLOWER
        self._reset_election_timer()

    # ------------------------------------------------------------------
    # Role Transitions
    # ------------------------------------------------------------------
    def xǁRaftNodeǁ_become_follower__mutmut_1(self, term: Optional[int] = None):
        if term is not None or term < self.current_term:
            return
        if term is not None and term > self.current_term:
            self.current_term = term
            self.voted_for = None
        if self.state != RaftState.FOLLOWER:
            logger.info(f"[{self.node_id}] -> FOLLOWER (term={self.current_term})")
        self.state = RaftState.FOLLOWER
        self._reset_election_timer()

    # ------------------------------------------------------------------
    # Role Transitions
    # ------------------------------------------------------------------
    def xǁRaftNodeǁ_become_follower__mutmut_2(self, term: Optional[int] = None):
        if term is None and term < self.current_term:
            return
        if term is not None and term > self.current_term:
            self.current_term = term
            self.voted_for = None
        if self.state != RaftState.FOLLOWER:
            logger.info(f"[{self.node_id}] -> FOLLOWER (term={self.current_term})")
        self.state = RaftState.FOLLOWER
        self._reset_election_timer()

    # ------------------------------------------------------------------
    # Role Transitions
    # ------------------------------------------------------------------
    def xǁRaftNodeǁ_become_follower__mutmut_3(self, term: Optional[int] = None):
        if term is not None and term <= self.current_term:
            return
        if term is not None and term > self.current_term:
            self.current_term = term
            self.voted_for = None
        if self.state != RaftState.FOLLOWER:
            logger.info(f"[{self.node_id}] -> FOLLOWER (term={self.current_term})")
        self.state = RaftState.FOLLOWER
        self._reset_election_timer()

    # ------------------------------------------------------------------
    # Role Transitions
    # ------------------------------------------------------------------
    def xǁRaftNodeǁ_become_follower__mutmut_4(self, term: Optional[int] = None):
        if term is not None and term < self.current_term:
            return
        if term is not None or term > self.current_term:
            self.current_term = term
            self.voted_for = None
        if self.state != RaftState.FOLLOWER:
            logger.info(f"[{self.node_id}] -> FOLLOWER (term={self.current_term})")
        self.state = RaftState.FOLLOWER
        self._reset_election_timer()

    # ------------------------------------------------------------------
    # Role Transitions
    # ------------------------------------------------------------------
    def xǁRaftNodeǁ_become_follower__mutmut_5(self, term: Optional[int] = None):
        if term is not None and term < self.current_term:
            return
        if term is None and term > self.current_term:
            self.current_term = term
            self.voted_for = None
        if self.state != RaftState.FOLLOWER:
            logger.info(f"[{self.node_id}] -> FOLLOWER (term={self.current_term})")
        self.state = RaftState.FOLLOWER
        self._reset_election_timer()

    # ------------------------------------------------------------------
    # Role Transitions
    # ------------------------------------------------------------------
    def xǁRaftNodeǁ_become_follower__mutmut_6(self, term: Optional[int] = None):
        if term is not None and term < self.current_term:
            return
        if term is not None and term >= self.current_term:
            self.current_term = term
            self.voted_for = None
        if self.state != RaftState.FOLLOWER:
            logger.info(f"[{self.node_id}] -> FOLLOWER (term={self.current_term})")
        self.state = RaftState.FOLLOWER
        self._reset_election_timer()

    # ------------------------------------------------------------------
    # Role Transitions
    # ------------------------------------------------------------------
    def xǁRaftNodeǁ_become_follower__mutmut_7(self, term: Optional[int] = None):
        if term is not None and term < self.current_term:
            return
        if term is not None and term > self.current_term:
            self.current_term = None
            self.voted_for = None
        if self.state != RaftState.FOLLOWER:
            logger.info(f"[{self.node_id}] -> FOLLOWER (term={self.current_term})")
        self.state = RaftState.FOLLOWER
        self._reset_election_timer()

    # ------------------------------------------------------------------
    # Role Transitions
    # ------------------------------------------------------------------
    def xǁRaftNodeǁ_become_follower__mutmut_8(self, term: Optional[int] = None):
        if term is not None and term < self.current_term:
            return
        if term is not None and term > self.current_term:
            self.current_term = term
            self.voted_for = ""
        if self.state != RaftState.FOLLOWER:
            logger.info(f"[{self.node_id}] -> FOLLOWER (term={self.current_term})")
        self.state = RaftState.FOLLOWER
        self._reset_election_timer()

    # ------------------------------------------------------------------
    # Role Transitions
    # ------------------------------------------------------------------
    def xǁRaftNodeǁ_become_follower__mutmut_9(self, term: Optional[int] = None):
        if term is not None and term < self.current_term:
            return
        if term is not None and term > self.current_term:
            self.current_term = term
            self.voted_for = None
        if self.state == RaftState.FOLLOWER:
            logger.info(f"[{self.node_id}] -> FOLLOWER (term={self.current_term})")
        self.state = RaftState.FOLLOWER
        self._reset_election_timer()

    # ------------------------------------------------------------------
    # Role Transitions
    # ------------------------------------------------------------------
    def xǁRaftNodeǁ_become_follower__mutmut_10(self, term: Optional[int] = None):
        if term is not None and term < self.current_term:
            return
        if term is not None and term > self.current_term:
            self.current_term = term
            self.voted_for = None
        if self.state != RaftState.FOLLOWER:
            logger.info(None)
        self.state = RaftState.FOLLOWER
        self._reset_election_timer()

    # ------------------------------------------------------------------
    # Role Transitions
    # ------------------------------------------------------------------
    def xǁRaftNodeǁ_become_follower__mutmut_11(self, term: Optional[int] = None):
        if term is not None and term < self.current_term:
            return
        if term is not None and term > self.current_term:
            self.current_term = term
            self.voted_for = None
        if self.state != RaftState.FOLLOWER:
            logger.info(f"[{self.node_id}] -> FOLLOWER (term={self.current_term})")
        self.state = None
        self._reset_election_timer()
    
    xǁRaftNodeǁ_become_follower__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁRaftNodeǁ_become_follower__mutmut_1': xǁRaftNodeǁ_become_follower__mutmut_1, 
        'xǁRaftNodeǁ_become_follower__mutmut_2': xǁRaftNodeǁ_become_follower__mutmut_2, 
        'xǁRaftNodeǁ_become_follower__mutmut_3': xǁRaftNodeǁ_become_follower__mutmut_3, 
        'xǁRaftNodeǁ_become_follower__mutmut_4': xǁRaftNodeǁ_become_follower__mutmut_4, 
        'xǁRaftNodeǁ_become_follower__mutmut_5': xǁRaftNodeǁ_become_follower__mutmut_5, 
        'xǁRaftNodeǁ_become_follower__mutmut_6': xǁRaftNodeǁ_become_follower__mutmut_6, 
        'xǁRaftNodeǁ_become_follower__mutmut_7': xǁRaftNodeǁ_become_follower__mutmut_7, 
        'xǁRaftNodeǁ_become_follower__mutmut_8': xǁRaftNodeǁ_become_follower__mutmut_8, 
        'xǁRaftNodeǁ_become_follower__mutmut_9': xǁRaftNodeǁ_become_follower__mutmut_9, 
        'xǁRaftNodeǁ_become_follower__mutmut_10': xǁRaftNodeǁ_become_follower__mutmut_10, 
        'xǁRaftNodeǁ_become_follower__mutmut_11': xǁRaftNodeǁ_become_follower__mutmut_11
    }
    
    def _become_follower(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁRaftNodeǁ_become_follower__mutmut_orig"), object.__getattribute__(self, "xǁRaftNodeǁ_become_follower__mutmut_mutants"), args, kwargs, self)
        return result 
    
    _become_follower.__signature__ = _mutmut_signature(xǁRaftNodeǁ_become_follower__mutmut_orig)
    xǁRaftNodeǁ_become_follower__mutmut_orig.__name__ = 'xǁRaftNodeǁ_become_follower'

    def xǁRaftNodeǁ_become_candidate__mutmut_orig(self):
        self.state = RaftState.CANDIDATE
        self.current_term += 1
        self.voted_for = self.node_id
        self._reset_election_timer()
        logger.info(f"[{self.node_id}] -> CANDIDATE (term={self.current_term})")

    def xǁRaftNodeǁ_become_candidate__mutmut_1(self):
        self.state = None
        self.current_term += 1
        self.voted_for = self.node_id
        self._reset_election_timer()
        logger.info(f"[{self.node_id}] -> CANDIDATE (term={self.current_term})")

    def xǁRaftNodeǁ_become_candidate__mutmut_2(self):
        self.state = RaftState.CANDIDATE
        self.current_term = 1
        self.voted_for = self.node_id
        self._reset_election_timer()
        logger.info(f"[{self.node_id}] -> CANDIDATE (term={self.current_term})")

    def xǁRaftNodeǁ_become_candidate__mutmut_3(self):
        self.state = RaftState.CANDIDATE
        self.current_term -= 1
        self.voted_for = self.node_id
        self._reset_election_timer()
        logger.info(f"[{self.node_id}] -> CANDIDATE (term={self.current_term})")

    def xǁRaftNodeǁ_become_candidate__mutmut_4(self):
        self.state = RaftState.CANDIDATE
        self.current_term += 2
        self.voted_for = self.node_id
        self._reset_election_timer()
        logger.info(f"[{self.node_id}] -> CANDIDATE (term={self.current_term})")

    def xǁRaftNodeǁ_become_candidate__mutmut_5(self):
        self.state = RaftState.CANDIDATE
        self.current_term += 1
        self.voted_for = None
        self._reset_election_timer()
        logger.info(f"[{self.node_id}] -> CANDIDATE (term={self.current_term})")

    def xǁRaftNodeǁ_become_candidate__mutmut_6(self):
        self.state = RaftState.CANDIDATE
        self.current_term += 1
        self.voted_for = self.node_id
        self._reset_election_timer()
        logger.info(None)
    
    xǁRaftNodeǁ_become_candidate__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁRaftNodeǁ_become_candidate__mutmut_1': xǁRaftNodeǁ_become_candidate__mutmut_1, 
        'xǁRaftNodeǁ_become_candidate__mutmut_2': xǁRaftNodeǁ_become_candidate__mutmut_2, 
        'xǁRaftNodeǁ_become_candidate__mutmut_3': xǁRaftNodeǁ_become_candidate__mutmut_3, 
        'xǁRaftNodeǁ_become_candidate__mutmut_4': xǁRaftNodeǁ_become_candidate__mutmut_4, 
        'xǁRaftNodeǁ_become_candidate__mutmut_5': xǁRaftNodeǁ_become_candidate__mutmut_5, 
        'xǁRaftNodeǁ_become_candidate__mutmut_6': xǁRaftNodeǁ_become_candidate__mutmut_6
    }
    
    def _become_candidate(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁRaftNodeǁ_become_candidate__mutmut_orig"), object.__getattribute__(self, "xǁRaftNodeǁ_become_candidate__mutmut_mutants"), args, kwargs, self)
        return result 
    
    _become_candidate.__signature__ = _mutmut_signature(xǁRaftNodeǁ_become_candidate__mutmut_orig)
    xǁRaftNodeǁ_become_candidate__mutmut_orig.__name__ = 'xǁRaftNodeǁ_become_candidate'

    def xǁRaftNodeǁ_become_leader__mutmut_orig(self):
        self.state = RaftState.LEADER
        # Initialize leader state
        for peer in self.peers:
            self.next_index[peer] = len(self.log)
            self.match_index[peer] = 0
        logger.info(f"[{self.node_id}] -> LEADER (term={self.current_term})")
        # Immediately send heartbeats
        self._send_heartbeats()

    def xǁRaftNodeǁ_become_leader__mutmut_1(self):
        self.state = None
        # Initialize leader state
        for peer in self.peers:
            self.next_index[peer] = len(self.log)
            self.match_index[peer] = 0
        logger.info(f"[{self.node_id}] -> LEADER (term={self.current_term})")
        # Immediately send heartbeats
        self._send_heartbeats()

    def xǁRaftNodeǁ_become_leader__mutmut_2(self):
        self.state = RaftState.LEADER
        # Initialize leader state
        for peer in self.peers:
            self.next_index[peer] = None
            self.match_index[peer] = 0
        logger.info(f"[{self.node_id}] -> LEADER (term={self.current_term})")
        # Immediately send heartbeats
        self._send_heartbeats()

    def xǁRaftNodeǁ_become_leader__mutmut_3(self):
        self.state = RaftState.LEADER
        # Initialize leader state
        for peer in self.peers:
            self.next_index[peer] = len(self.log)
            self.match_index[peer] = None
        logger.info(f"[{self.node_id}] -> LEADER (term={self.current_term})")
        # Immediately send heartbeats
        self._send_heartbeats()

    def xǁRaftNodeǁ_become_leader__mutmut_4(self):
        self.state = RaftState.LEADER
        # Initialize leader state
        for peer in self.peers:
            self.next_index[peer] = len(self.log)
            self.match_index[peer] = 1
        logger.info(f"[{self.node_id}] -> LEADER (term={self.current_term})")
        # Immediately send heartbeats
        self._send_heartbeats()

    def xǁRaftNodeǁ_become_leader__mutmut_5(self):
        self.state = RaftState.LEADER
        # Initialize leader state
        for peer in self.peers:
            self.next_index[peer] = len(self.log)
            self.match_index[peer] = 0
        logger.info(None)
        # Immediately send heartbeats
        self._send_heartbeats()
    
    xǁRaftNodeǁ_become_leader__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁRaftNodeǁ_become_leader__mutmut_1': xǁRaftNodeǁ_become_leader__mutmut_1, 
        'xǁRaftNodeǁ_become_leader__mutmut_2': xǁRaftNodeǁ_become_leader__mutmut_2, 
        'xǁRaftNodeǁ_become_leader__mutmut_3': xǁRaftNodeǁ_become_leader__mutmut_3, 
        'xǁRaftNodeǁ_become_leader__mutmut_4': xǁRaftNodeǁ_become_leader__mutmut_4, 
        'xǁRaftNodeǁ_become_leader__mutmut_5': xǁRaftNodeǁ_become_leader__mutmut_5
    }
    
    def _become_leader(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁRaftNodeǁ_become_leader__mutmut_orig"), object.__getattribute__(self, "xǁRaftNodeǁ_become_leader__mutmut_mutants"), args, kwargs, self)
        return result 
    
    _become_leader.__signature__ = _mutmut_signature(xǁRaftNodeǁ_become_leader__mutmut_orig)
    xǁRaftNodeǁ_become_leader__mutmut_orig.__name__ = 'xǁRaftNodeǁ_become_leader'

    # ------------------------------------------------------------------
    # Elections
    # ------------------------------------------------------------------
    def xǁRaftNodeǁstart_election__mutmut_orig(self) -> bool:
        self._become_candidate()
        votes = 1  # self vote
        last_log_index = len(self.log) - 1
        last_log_term = self.log[last_log_index].term
        for peer in self.peers:
            if self._request_vote_rpc(peer, self.current_term, last_log_index, last_log_term):
                votes += 1
        if votes > len(self.peers) // 2:  # majority
            self._become_leader()
            return True
        return False

    # ------------------------------------------------------------------
    # Elections
    # ------------------------------------------------------------------
    def xǁRaftNodeǁstart_election__mutmut_1(self) -> bool:
        self._become_candidate()
        votes = None  # self vote
        last_log_index = len(self.log) - 1
        last_log_term = self.log[last_log_index].term
        for peer in self.peers:
            if self._request_vote_rpc(peer, self.current_term, last_log_index, last_log_term):
                votes += 1
        if votes > len(self.peers) // 2:  # majority
            self._become_leader()
            return True
        return False

    # ------------------------------------------------------------------
    # Elections
    # ------------------------------------------------------------------
    def xǁRaftNodeǁstart_election__mutmut_2(self) -> bool:
        self._become_candidate()
        votes = 2  # self vote
        last_log_index = len(self.log) - 1
        last_log_term = self.log[last_log_index].term
        for peer in self.peers:
            if self._request_vote_rpc(peer, self.current_term, last_log_index, last_log_term):
                votes += 1
        if votes > len(self.peers) // 2:  # majority
            self._become_leader()
            return True
        return False

    # ------------------------------------------------------------------
    # Elections
    # ------------------------------------------------------------------
    def xǁRaftNodeǁstart_election__mutmut_3(self) -> bool:
        self._become_candidate()
        votes = 1  # self vote
        last_log_index = None
        last_log_term = self.log[last_log_index].term
        for peer in self.peers:
            if self._request_vote_rpc(peer, self.current_term, last_log_index, last_log_term):
                votes += 1
        if votes > len(self.peers) // 2:  # majority
            self._become_leader()
            return True
        return False

    # ------------------------------------------------------------------
    # Elections
    # ------------------------------------------------------------------
    def xǁRaftNodeǁstart_election__mutmut_4(self) -> bool:
        self._become_candidate()
        votes = 1  # self vote
        last_log_index = len(self.log) + 1
        last_log_term = self.log[last_log_index].term
        for peer in self.peers:
            if self._request_vote_rpc(peer, self.current_term, last_log_index, last_log_term):
                votes += 1
        if votes > len(self.peers) // 2:  # majority
            self._become_leader()
            return True
        return False

    # ------------------------------------------------------------------
    # Elections
    # ------------------------------------------------------------------
    def xǁRaftNodeǁstart_election__mutmut_5(self) -> bool:
        self._become_candidate()
        votes = 1  # self vote
        last_log_index = len(self.log) - 2
        last_log_term = self.log[last_log_index].term
        for peer in self.peers:
            if self._request_vote_rpc(peer, self.current_term, last_log_index, last_log_term):
                votes += 1
        if votes > len(self.peers) // 2:  # majority
            self._become_leader()
            return True
        return False

    # ------------------------------------------------------------------
    # Elections
    # ------------------------------------------------------------------
    def xǁRaftNodeǁstart_election__mutmut_6(self) -> bool:
        self._become_candidate()
        votes = 1  # self vote
        last_log_index = len(self.log) - 1
        last_log_term = None
        for peer in self.peers:
            if self._request_vote_rpc(peer, self.current_term, last_log_index, last_log_term):
                votes += 1
        if votes > len(self.peers) // 2:  # majority
            self._become_leader()
            return True
        return False

    # ------------------------------------------------------------------
    # Elections
    # ------------------------------------------------------------------
    def xǁRaftNodeǁstart_election__mutmut_7(self) -> bool:
        self._become_candidate()
        votes = 1  # self vote
        last_log_index = len(self.log) - 1
        last_log_term = self.log[last_log_index].term
        for peer in self.peers:
            if self._request_vote_rpc(None, self.current_term, last_log_index, last_log_term):
                votes += 1
        if votes > len(self.peers) // 2:  # majority
            self._become_leader()
            return True
        return False

    # ------------------------------------------------------------------
    # Elections
    # ------------------------------------------------------------------
    def xǁRaftNodeǁstart_election__mutmut_8(self) -> bool:
        self._become_candidate()
        votes = 1  # self vote
        last_log_index = len(self.log) - 1
        last_log_term = self.log[last_log_index].term
        for peer in self.peers:
            if self._request_vote_rpc(peer, None, last_log_index, last_log_term):
                votes += 1
        if votes > len(self.peers) // 2:  # majority
            self._become_leader()
            return True
        return False

    # ------------------------------------------------------------------
    # Elections
    # ------------------------------------------------------------------
    def xǁRaftNodeǁstart_election__mutmut_9(self) -> bool:
        self._become_candidate()
        votes = 1  # self vote
        last_log_index = len(self.log) - 1
        last_log_term = self.log[last_log_index].term
        for peer in self.peers:
            if self._request_vote_rpc(peer, self.current_term, None, last_log_term):
                votes += 1
        if votes > len(self.peers) // 2:  # majority
            self._become_leader()
            return True
        return False

    # ------------------------------------------------------------------
    # Elections
    # ------------------------------------------------------------------
    def xǁRaftNodeǁstart_election__mutmut_10(self) -> bool:
        self._become_candidate()
        votes = 1  # self vote
        last_log_index = len(self.log) - 1
        last_log_term = self.log[last_log_index].term
        for peer in self.peers:
            if self._request_vote_rpc(peer, self.current_term, last_log_index, None):
                votes += 1
        if votes > len(self.peers) // 2:  # majority
            self._become_leader()
            return True
        return False

    # ------------------------------------------------------------------
    # Elections
    # ------------------------------------------------------------------
    def xǁRaftNodeǁstart_election__mutmut_11(self) -> bool:
        self._become_candidate()
        votes = 1  # self vote
        last_log_index = len(self.log) - 1
        last_log_term = self.log[last_log_index].term
        for peer in self.peers:
            if self._request_vote_rpc(self.current_term, last_log_index, last_log_term):
                votes += 1
        if votes > len(self.peers) // 2:  # majority
            self._become_leader()
            return True
        return False

    # ------------------------------------------------------------------
    # Elections
    # ------------------------------------------------------------------
    def xǁRaftNodeǁstart_election__mutmut_12(self) -> bool:
        self._become_candidate()
        votes = 1  # self vote
        last_log_index = len(self.log) - 1
        last_log_term = self.log[last_log_index].term
        for peer in self.peers:
            if self._request_vote_rpc(peer, last_log_index, last_log_term):
                votes += 1
        if votes > len(self.peers) // 2:  # majority
            self._become_leader()
            return True
        return False

    # ------------------------------------------------------------------
    # Elections
    # ------------------------------------------------------------------
    def xǁRaftNodeǁstart_election__mutmut_13(self) -> bool:
        self._become_candidate()
        votes = 1  # self vote
        last_log_index = len(self.log) - 1
        last_log_term = self.log[last_log_index].term
        for peer in self.peers:
            if self._request_vote_rpc(peer, self.current_term, last_log_term):
                votes += 1
        if votes > len(self.peers) // 2:  # majority
            self._become_leader()
            return True
        return False

    # ------------------------------------------------------------------
    # Elections
    # ------------------------------------------------------------------
    def xǁRaftNodeǁstart_election__mutmut_14(self) -> bool:
        self._become_candidate()
        votes = 1  # self vote
        last_log_index = len(self.log) - 1
        last_log_term = self.log[last_log_index].term
        for peer in self.peers:
            if self._request_vote_rpc(peer, self.current_term, last_log_index, ):
                votes += 1
        if votes > len(self.peers) // 2:  # majority
            self._become_leader()
            return True
        return False

    # ------------------------------------------------------------------
    # Elections
    # ------------------------------------------------------------------
    def xǁRaftNodeǁstart_election__mutmut_15(self) -> bool:
        self._become_candidate()
        votes = 1  # self vote
        last_log_index = len(self.log) - 1
        last_log_term = self.log[last_log_index].term
        for peer in self.peers:
            if self._request_vote_rpc(peer, self.current_term, last_log_index, last_log_term):
                votes = 1
        if votes > len(self.peers) // 2:  # majority
            self._become_leader()
            return True
        return False

    # ------------------------------------------------------------------
    # Elections
    # ------------------------------------------------------------------
    def xǁRaftNodeǁstart_election__mutmut_16(self) -> bool:
        self._become_candidate()
        votes = 1  # self vote
        last_log_index = len(self.log) - 1
        last_log_term = self.log[last_log_index].term
        for peer in self.peers:
            if self._request_vote_rpc(peer, self.current_term, last_log_index, last_log_term):
                votes -= 1
        if votes > len(self.peers) // 2:  # majority
            self._become_leader()
            return True
        return False

    # ------------------------------------------------------------------
    # Elections
    # ------------------------------------------------------------------
    def xǁRaftNodeǁstart_election__mutmut_17(self) -> bool:
        self._become_candidate()
        votes = 1  # self vote
        last_log_index = len(self.log) - 1
        last_log_term = self.log[last_log_index].term
        for peer in self.peers:
            if self._request_vote_rpc(peer, self.current_term, last_log_index, last_log_term):
                votes += 2
        if votes > len(self.peers) // 2:  # majority
            self._become_leader()
            return True
        return False

    # ------------------------------------------------------------------
    # Elections
    # ------------------------------------------------------------------
    def xǁRaftNodeǁstart_election__mutmut_18(self) -> bool:
        self._become_candidate()
        votes = 1  # self vote
        last_log_index = len(self.log) - 1
        last_log_term = self.log[last_log_index].term
        for peer in self.peers:
            if self._request_vote_rpc(peer, self.current_term, last_log_index, last_log_term):
                votes += 1
        if votes >= len(self.peers) // 2:  # majority
            self._become_leader()
            return True
        return False

    # ------------------------------------------------------------------
    # Elections
    # ------------------------------------------------------------------
    def xǁRaftNodeǁstart_election__mutmut_19(self) -> bool:
        self._become_candidate()
        votes = 1  # self vote
        last_log_index = len(self.log) - 1
        last_log_term = self.log[last_log_index].term
        for peer in self.peers:
            if self._request_vote_rpc(peer, self.current_term, last_log_index, last_log_term):
                votes += 1
        if votes > len(self.peers) / 2:  # majority
            self._become_leader()
            return True
        return False

    # ------------------------------------------------------------------
    # Elections
    # ------------------------------------------------------------------
    def xǁRaftNodeǁstart_election__mutmut_20(self) -> bool:
        self._become_candidate()
        votes = 1  # self vote
        last_log_index = len(self.log) - 1
        last_log_term = self.log[last_log_index].term
        for peer in self.peers:
            if self._request_vote_rpc(peer, self.current_term, last_log_index, last_log_term):
                votes += 1
        if votes > len(self.peers) // 3:  # majority
            self._become_leader()
            return True
        return False

    # ------------------------------------------------------------------
    # Elections
    # ------------------------------------------------------------------
    def xǁRaftNodeǁstart_election__mutmut_21(self) -> bool:
        self._become_candidate()
        votes = 1  # self vote
        last_log_index = len(self.log) - 1
        last_log_term = self.log[last_log_index].term
        for peer in self.peers:
            if self._request_vote_rpc(peer, self.current_term, last_log_index, last_log_term):
                votes += 1
        if votes > len(self.peers) // 2:  # majority
            self._become_leader()
            return False
        return False

    # ------------------------------------------------------------------
    # Elections
    # ------------------------------------------------------------------
    def xǁRaftNodeǁstart_election__mutmut_22(self) -> bool:
        self._become_candidate()
        votes = 1  # self vote
        last_log_index = len(self.log) - 1
        last_log_term = self.log[last_log_index].term
        for peer in self.peers:
            if self._request_vote_rpc(peer, self.current_term, last_log_index, last_log_term):
                votes += 1
        if votes > len(self.peers) // 2:  # majority
            self._become_leader()
            return True
        return True
    
    xǁRaftNodeǁstart_election__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁRaftNodeǁstart_election__mutmut_1': xǁRaftNodeǁstart_election__mutmut_1, 
        'xǁRaftNodeǁstart_election__mutmut_2': xǁRaftNodeǁstart_election__mutmut_2, 
        'xǁRaftNodeǁstart_election__mutmut_3': xǁRaftNodeǁstart_election__mutmut_3, 
        'xǁRaftNodeǁstart_election__mutmut_4': xǁRaftNodeǁstart_election__mutmut_4, 
        'xǁRaftNodeǁstart_election__mutmut_5': xǁRaftNodeǁstart_election__mutmut_5, 
        'xǁRaftNodeǁstart_election__mutmut_6': xǁRaftNodeǁstart_election__mutmut_6, 
        'xǁRaftNodeǁstart_election__mutmut_7': xǁRaftNodeǁstart_election__mutmut_7, 
        'xǁRaftNodeǁstart_election__mutmut_8': xǁRaftNodeǁstart_election__mutmut_8, 
        'xǁRaftNodeǁstart_election__mutmut_9': xǁRaftNodeǁstart_election__mutmut_9, 
        'xǁRaftNodeǁstart_election__mutmut_10': xǁRaftNodeǁstart_election__mutmut_10, 
        'xǁRaftNodeǁstart_election__mutmut_11': xǁRaftNodeǁstart_election__mutmut_11, 
        'xǁRaftNodeǁstart_election__mutmut_12': xǁRaftNodeǁstart_election__mutmut_12, 
        'xǁRaftNodeǁstart_election__mutmut_13': xǁRaftNodeǁstart_election__mutmut_13, 
        'xǁRaftNodeǁstart_election__mutmut_14': xǁRaftNodeǁstart_election__mutmut_14, 
        'xǁRaftNodeǁstart_election__mutmut_15': xǁRaftNodeǁstart_election__mutmut_15, 
        'xǁRaftNodeǁstart_election__mutmut_16': xǁRaftNodeǁstart_election__mutmut_16, 
        'xǁRaftNodeǁstart_election__mutmut_17': xǁRaftNodeǁstart_election__mutmut_17, 
        'xǁRaftNodeǁstart_election__mutmut_18': xǁRaftNodeǁstart_election__mutmut_18, 
        'xǁRaftNodeǁstart_election__mutmut_19': xǁRaftNodeǁstart_election__mutmut_19, 
        'xǁRaftNodeǁstart_election__mutmut_20': xǁRaftNodeǁstart_election__mutmut_20, 
        'xǁRaftNodeǁstart_election__mutmut_21': xǁRaftNodeǁstart_election__mutmut_21, 
        'xǁRaftNodeǁstart_election__mutmut_22': xǁRaftNodeǁstart_election__mutmut_22
    }
    
    def start_election(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁRaftNodeǁstart_election__mutmut_orig"), object.__getattribute__(self, "xǁRaftNodeǁstart_election__mutmut_mutants"), args, kwargs, self)
        return result 
    
    start_election.__signature__ = _mutmut_signature(xǁRaftNodeǁstart_election__mutmut_orig)
    xǁRaftNodeǁstart_election__mutmut_orig.__name__ = 'xǁRaftNodeǁstart_election'

    def xǁRaftNodeǁ_request_vote_rpc__mutmut_orig(self, peer: str, term: int, last_log_index: int, last_log_term: int) -> bool:
        # Simulated vote: peer grants with 95% probability for reliable tests
        chance = self.rng.random()
        granted = chance < 0.95
        logger.debug(f"[{self.node_id}] RequestVote -> {peer} granted={granted} (p={chance:.2f})")
        return granted

    def xǁRaftNodeǁ_request_vote_rpc__mutmut_1(self, peer: str, term: int, last_log_index: int, last_log_term: int) -> bool:
        # Simulated vote: peer grants with 95% probability for reliable tests
        chance = None
        granted = chance < 0.95
        logger.debug(f"[{self.node_id}] RequestVote -> {peer} granted={granted} (p={chance:.2f})")
        return granted

    def xǁRaftNodeǁ_request_vote_rpc__mutmut_2(self, peer: str, term: int, last_log_index: int, last_log_term: int) -> bool:
        # Simulated vote: peer grants with 95% probability for reliable tests
        chance = self.rng.random()
        granted = None
        logger.debug(f"[{self.node_id}] RequestVote -> {peer} granted={granted} (p={chance:.2f})")
        return granted

    def xǁRaftNodeǁ_request_vote_rpc__mutmut_3(self, peer: str, term: int, last_log_index: int, last_log_term: int) -> bool:
        # Simulated vote: peer grants with 95% probability for reliable tests
        chance = self.rng.random()
        granted = chance <= 0.95
        logger.debug(f"[{self.node_id}] RequestVote -> {peer} granted={granted} (p={chance:.2f})")
        return granted

    def xǁRaftNodeǁ_request_vote_rpc__mutmut_4(self, peer: str, term: int, last_log_index: int, last_log_term: int) -> bool:
        # Simulated vote: peer grants with 95% probability for reliable tests
        chance = self.rng.random()
        granted = chance < 1.95
        logger.debug(f"[{self.node_id}] RequestVote -> {peer} granted={granted} (p={chance:.2f})")
        return granted

    def xǁRaftNodeǁ_request_vote_rpc__mutmut_5(self, peer: str, term: int, last_log_index: int, last_log_term: int) -> bool:
        # Simulated vote: peer grants with 95% probability for reliable tests
        chance = self.rng.random()
        granted = chance < 0.95
        logger.debug(None)
        return granted
    
    xǁRaftNodeǁ_request_vote_rpc__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁRaftNodeǁ_request_vote_rpc__mutmut_1': xǁRaftNodeǁ_request_vote_rpc__mutmut_1, 
        'xǁRaftNodeǁ_request_vote_rpc__mutmut_2': xǁRaftNodeǁ_request_vote_rpc__mutmut_2, 
        'xǁRaftNodeǁ_request_vote_rpc__mutmut_3': xǁRaftNodeǁ_request_vote_rpc__mutmut_3, 
        'xǁRaftNodeǁ_request_vote_rpc__mutmut_4': xǁRaftNodeǁ_request_vote_rpc__mutmut_4, 
        'xǁRaftNodeǁ_request_vote_rpc__mutmut_5': xǁRaftNodeǁ_request_vote_rpc__mutmut_5
    }
    
    def _request_vote_rpc(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁRaftNodeǁ_request_vote_rpc__mutmut_orig"), object.__getattribute__(self, "xǁRaftNodeǁ_request_vote_rpc__mutmut_mutants"), args, kwargs, self)
        return result 
    
    _request_vote_rpc.__signature__ = _mutmut_signature(xǁRaftNodeǁ_request_vote_rpc__mutmut_orig)
    xǁRaftNodeǁ_request_vote_rpc__mutmut_orig.__name__ = 'xǁRaftNodeǁ_request_vote_rpc'

    # ------------------------------------------------------------------
    # Heartbeats & Replication
    # ------------------------------------------------------------------
    def xǁRaftNodeǁ_send_heartbeats__mutmut_orig(self):
        self.last_heartbeat = datetime.now()
        for peer in self.peers:
            self._append_entries_rpc(peer, heartbeat=True)

    # ------------------------------------------------------------------
    # Heartbeats & Replication
    # ------------------------------------------------------------------
    def xǁRaftNodeǁ_send_heartbeats__mutmut_1(self):
        self.last_heartbeat = None
        for peer in self.peers:
            self._append_entries_rpc(peer, heartbeat=True)

    # ------------------------------------------------------------------
    # Heartbeats & Replication
    # ------------------------------------------------------------------
    def xǁRaftNodeǁ_send_heartbeats__mutmut_2(self):
        self.last_heartbeat = datetime.now()
        for peer in self.peers:
            self._append_entries_rpc(None, heartbeat=True)

    # ------------------------------------------------------------------
    # Heartbeats & Replication
    # ------------------------------------------------------------------
    def xǁRaftNodeǁ_send_heartbeats__mutmut_3(self):
        self.last_heartbeat = datetime.now()
        for peer in self.peers:
            self._append_entries_rpc(peer, heartbeat=None)

    # ------------------------------------------------------------------
    # Heartbeats & Replication
    # ------------------------------------------------------------------
    def xǁRaftNodeǁ_send_heartbeats__mutmut_4(self):
        self.last_heartbeat = datetime.now()
        for peer in self.peers:
            self._append_entries_rpc(heartbeat=True)

    # ------------------------------------------------------------------
    # Heartbeats & Replication
    # ------------------------------------------------------------------
    def xǁRaftNodeǁ_send_heartbeats__mutmut_5(self):
        self.last_heartbeat = datetime.now()
        for peer in self.peers:
            self._append_entries_rpc(peer, )

    # ------------------------------------------------------------------
    # Heartbeats & Replication
    # ------------------------------------------------------------------
    def xǁRaftNodeǁ_send_heartbeats__mutmut_6(self):
        self.last_heartbeat = datetime.now()
        for peer in self.peers:
            self._append_entries_rpc(peer, heartbeat=False)
    
    xǁRaftNodeǁ_send_heartbeats__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁRaftNodeǁ_send_heartbeats__mutmut_1': xǁRaftNodeǁ_send_heartbeats__mutmut_1, 
        'xǁRaftNodeǁ_send_heartbeats__mutmut_2': xǁRaftNodeǁ_send_heartbeats__mutmut_2, 
        'xǁRaftNodeǁ_send_heartbeats__mutmut_3': xǁRaftNodeǁ_send_heartbeats__mutmut_3, 
        'xǁRaftNodeǁ_send_heartbeats__mutmut_4': xǁRaftNodeǁ_send_heartbeats__mutmut_4, 
        'xǁRaftNodeǁ_send_heartbeats__mutmut_5': xǁRaftNodeǁ_send_heartbeats__mutmut_5, 
        'xǁRaftNodeǁ_send_heartbeats__mutmut_6': xǁRaftNodeǁ_send_heartbeats__mutmut_6
    }
    
    def _send_heartbeats(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁRaftNodeǁ_send_heartbeats__mutmut_orig"), object.__getattribute__(self, "xǁRaftNodeǁ_send_heartbeats__mutmut_mutants"), args, kwargs, self)
        return result 
    
    _send_heartbeats.__signature__ = _mutmut_signature(xǁRaftNodeǁ_send_heartbeats__mutmut_orig)
    xǁRaftNodeǁ_send_heartbeats__mutmut_orig.__name__ = 'xǁRaftNodeǁ_send_heartbeats'

    def xǁRaftNodeǁappend_entry__mutmut_orig(self, command: Any) -> bool:
        if self.state != RaftState.LEADER:
            logger.warning(f"[{self.node_id}] Reject append: not leader")
            return False
        entry = LogEntry(term=self.current_term, index=len(self.log), command=command)
        self.log.append(entry)
        logger.info(f"[{self.node_id}] Appended log index={entry.index} term={entry.term}")
        self._replicate()
        return True

    def xǁRaftNodeǁappend_entry__mutmut_1(self, command: Any) -> bool:
        if self.state == RaftState.LEADER:
            logger.warning(f"[{self.node_id}] Reject append: not leader")
            return False
        entry = LogEntry(term=self.current_term, index=len(self.log), command=command)
        self.log.append(entry)
        logger.info(f"[{self.node_id}] Appended log index={entry.index} term={entry.term}")
        self._replicate()
        return True

    def xǁRaftNodeǁappend_entry__mutmut_2(self, command: Any) -> bool:
        if self.state != RaftState.LEADER:
            logger.warning(None)
            return False
        entry = LogEntry(term=self.current_term, index=len(self.log), command=command)
        self.log.append(entry)
        logger.info(f"[{self.node_id}] Appended log index={entry.index} term={entry.term}")
        self._replicate()
        return True

    def xǁRaftNodeǁappend_entry__mutmut_3(self, command: Any) -> bool:
        if self.state != RaftState.LEADER:
            logger.warning(f"[{self.node_id}] Reject append: not leader")
            return True
        entry = LogEntry(term=self.current_term, index=len(self.log), command=command)
        self.log.append(entry)
        logger.info(f"[{self.node_id}] Appended log index={entry.index} term={entry.term}")
        self._replicate()
        return True

    def xǁRaftNodeǁappend_entry__mutmut_4(self, command: Any) -> bool:
        if self.state != RaftState.LEADER:
            logger.warning(f"[{self.node_id}] Reject append: not leader")
            return False
        entry = None
        self.log.append(entry)
        logger.info(f"[{self.node_id}] Appended log index={entry.index} term={entry.term}")
        self._replicate()
        return True

    def xǁRaftNodeǁappend_entry__mutmut_5(self, command: Any) -> bool:
        if self.state != RaftState.LEADER:
            logger.warning(f"[{self.node_id}] Reject append: not leader")
            return False
        entry = LogEntry(term=None, index=len(self.log), command=command)
        self.log.append(entry)
        logger.info(f"[{self.node_id}] Appended log index={entry.index} term={entry.term}")
        self._replicate()
        return True

    def xǁRaftNodeǁappend_entry__mutmut_6(self, command: Any) -> bool:
        if self.state != RaftState.LEADER:
            logger.warning(f"[{self.node_id}] Reject append: not leader")
            return False
        entry = LogEntry(term=self.current_term, index=None, command=command)
        self.log.append(entry)
        logger.info(f"[{self.node_id}] Appended log index={entry.index} term={entry.term}")
        self._replicate()
        return True

    def xǁRaftNodeǁappend_entry__mutmut_7(self, command: Any) -> bool:
        if self.state != RaftState.LEADER:
            logger.warning(f"[{self.node_id}] Reject append: not leader")
            return False
        entry = LogEntry(term=self.current_term, index=len(self.log), command=None)
        self.log.append(entry)
        logger.info(f"[{self.node_id}] Appended log index={entry.index} term={entry.term}")
        self._replicate()
        return True

    def xǁRaftNodeǁappend_entry__mutmut_8(self, command: Any) -> bool:
        if self.state != RaftState.LEADER:
            logger.warning(f"[{self.node_id}] Reject append: not leader")
            return False
        entry = LogEntry(index=len(self.log), command=command)
        self.log.append(entry)
        logger.info(f"[{self.node_id}] Appended log index={entry.index} term={entry.term}")
        self._replicate()
        return True

    def xǁRaftNodeǁappend_entry__mutmut_9(self, command: Any) -> bool:
        if self.state != RaftState.LEADER:
            logger.warning(f"[{self.node_id}] Reject append: not leader")
            return False
        entry = LogEntry(term=self.current_term, command=command)
        self.log.append(entry)
        logger.info(f"[{self.node_id}] Appended log index={entry.index} term={entry.term}")
        self._replicate()
        return True

    def xǁRaftNodeǁappend_entry__mutmut_10(self, command: Any) -> bool:
        if self.state != RaftState.LEADER:
            logger.warning(f"[{self.node_id}] Reject append: not leader")
            return False
        entry = LogEntry(term=self.current_term, index=len(self.log), )
        self.log.append(entry)
        logger.info(f"[{self.node_id}] Appended log index={entry.index} term={entry.term}")
        self._replicate()
        return True

    def xǁRaftNodeǁappend_entry__mutmut_11(self, command: Any) -> bool:
        if self.state != RaftState.LEADER:
            logger.warning(f"[{self.node_id}] Reject append: not leader")
            return False
        entry = LogEntry(term=self.current_term, index=len(self.log), command=command)
        self.log.append(None)
        logger.info(f"[{self.node_id}] Appended log index={entry.index} term={entry.term}")
        self._replicate()
        return True

    def xǁRaftNodeǁappend_entry__mutmut_12(self, command: Any) -> bool:
        if self.state != RaftState.LEADER:
            logger.warning(f"[{self.node_id}] Reject append: not leader")
            return False
        entry = LogEntry(term=self.current_term, index=len(self.log), command=command)
        self.log.append(entry)
        logger.info(None)
        self._replicate()
        return True

    def xǁRaftNodeǁappend_entry__mutmut_13(self, command: Any) -> bool:
        if self.state != RaftState.LEADER:
            logger.warning(f"[{self.node_id}] Reject append: not leader")
            return False
        entry = LogEntry(term=self.current_term, index=len(self.log), command=command)
        self.log.append(entry)
        logger.info(f"[{self.node_id}] Appended log index={entry.index} term={entry.term}")
        self._replicate()
        return False
    
    xǁRaftNodeǁappend_entry__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁRaftNodeǁappend_entry__mutmut_1': xǁRaftNodeǁappend_entry__mutmut_1, 
        'xǁRaftNodeǁappend_entry__mutmut_2': xǁRaftNodeǁappend_entry__mutmut_2, 
        'xǁRaftNodeǁappend_entry__mutmut_3': xǁRaftNodeǁappend_entry__mutmut_3, 
        'xǁRaftNodeǁappend_entry__mutmut_4': xǁRaftNodeǁappend_entry__mutmut_4, 
        'xǁRaftNodeǁappend_entry__mutmut_5': xǁRaftNodeǁappend_entry__mutmut_5, 
        'xǁRaftNodeǁappend_entry__mutmut_6': xǁRaftNodeǁappend_entry__mutmut_6, 
        'xǁRaftNodeǁappend_entry__mutmut_7': xǁRaftNodeǁappend_entry__mutmut_7, 
        'xǁRaftNodeǁappend_entry__mutmut_8': xǁRaftNodeǁappend_entry__mutmut_8, 
        'xǁRaftNodeǁappend_entry__mutmut_9': xǁRaftNodeǁappend_entry__mutmut_9, 
        'xǁRaftNodeǁappend_entry__mutmut_10': xǁRaftNodeǁappend_entry__mutmut_10, 
        'xǁRaftNodeǁappend_entry__mutmut_11': xǁRaftNodeǁappend_entry__mutmut_11, 
        'xǁRaftNodeǁappend_entry__mutmut_12': xǁRaftNodeǁappend_entry__mutmut_12, 
        'xǁRaftNodeǁappend_entry__mutmut_13': xǁRaftNodeǁappend_entry__mutmut_13
    }
    
    def append_entry(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁRaftNodeǁappend_entry__mutmut_orig"), object.__getattribute__(self, "xǁRaftNodeǁappend_entry__mutmut_mutants"), args, kwargs, self)
        return result 
    
    append_entry.__signature__ = _mutmut_signature(xǁRaftNodeǁappend_entry__mutmut_orig)
    xǁRaftNodeǁappend_entry__mutmut_orig.__name__ = 'xǁRaftNodeǁappend_entry'

    def xǁRaftNodeǁ_replicate__mutmut_orig(self):
        for peer in self.peers:
            self._append_entries_rpc(peer)
        self._advance_commit_index()

    def xǁRaftNodeǁ_replicate__mutmut_1(self):
        for peer in self.peers:
            self._append_entries_rpc(None)
        self._advance_commit_index()
    
    xǁRaftNodeǁ_replicate__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁRaftNodeǁ_replicate__mutmut_1': xǁRaftNodeǁ_replicate__mutmut_1
    }
    
    def _replicate(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁRaftNodeǁ_replicate__mutmut_orig"), object.__getattribute__(self, "xǁRaftNodeǁ_replicate__mutmut_mutants"), args, kwargs, self)
        return result 
    
    _replicate.__signature__ = _mutmut_signature(xǁRaftNodeǁ_replicate__mutmut_orig)
    xǁRaftNodeǁ_replicate__mutmut_orig.__name__ = 'xǁRaftNodeǁ_replicate'

    def xǁRaftNodeǁ_append_entries_rpc__mutmut_orig(self, peer: str, heartbeat: bool = False) -> bool:
        prev_index = self.next_index[peer] - 1
        prev_term = self.log[prev_index].term if prev_index < len(self.log) else 0
        entries = [] if heartbeat else self.log[self.next_index[peer]:]
        # Simulate success with 80% reliability
        success = self.rng.random() < 0.8
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
            f"[{self.node_id}] AppendEntries -> {peer} success={success} hb={heartbeat} prev=({prev_index},{prev_term}) send={len(entries)} next_index={self.next_index[peer]}"
        )
        return success

    def xǁRaftNodeǁ_append_entries_rpc__mutmut_1(self, peer: str, heartbeat: bool = True) -> bool:
        prev_index = self.next_index[peer] - 1
        prev_term = self.log[prev_index].term if prev_index < len(self.log) else 0
        entries = [] if heartbeat else self.log[self.next_index[peer]:]
        # Simulate success with 80% reliability
        success = self.rng.random() < 0.8
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
            f"[{self.node_id}] AppendEntries -> {peer} success={success} hb={heartbeat} prev=({prev_index},{prev_term}) send={len(entries)} next_index={self.next_index[peer]}"
        )
        return success

    def xǁRaftNodeǁ_append_entries_rpc__mutmut_2(self, peer: str, heartbeat: bool = False) -> bool:
        prev_index = None
        prev_term = self.log[prev_index].term if prev_index < len(self.log) else 0
        entries = [] if heartbeat else self.log[self.next_index[peer]:]
        # Simulate success with 80% reliability
        success = self.rng.random() < 0.8
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
            f"[{self.node_id}] AppendEntries -> {peer} success={success} hb={heartbeat} prev=({prev_index},{prev_term}) send={len(entries)} next_index={self.next_index[peer]}"
        )
        return success

    def xǁRaftNodeǁ_append_entries_rpc__mutmut_3(self, peer: str, heartbeat: bool = False) -> bool:
        prev_index = self.next_index[peer] + 1
        prev_term = self.log[prev_index].term if prev_index < len(self.log) else 0
        entries = [] if heartbeat else self.log[self.next_index[peer]:]
        # Simulate success with 80% reliability
        success = self.rng.random() < 0.8
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
            f"[{self.node_id}] AppendEntries -> {peer} success={success} hb={heartbeat} prev=({prev_index},{prev_term}) send={len(entries)} next_index={self.next_index[peer]}"
        )
        return success

    def xǁRaftNodeǁ_append_entries_rpc__mutmut_4(self, peer: str, heartbeat: bool = False) -> bool:
        prev_index = self.next_index[peer] - 2
        prev_term = self.log[prev_index].term if prev_index < len(self.log) else 0
        entries = [] if heartbeat else self.log[self.next_index[peer]:]
        # Simulate success with 80% reliability
        success = self.rng.random() < 0.8
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
            f"[{self.node_id}] AppendEntries -> {peer} success={success} hb={heartbeat} prev=({prev_index},{prev_term}) send={len(entries)} next_index={self.next_index[peer]}"
        )
        return success

    def xǁRaftNodeǁ_append_entries_rpc__mutmut_5(self, peer: str, heartbeat: bool = False) -> bool:
        prev_index = self.next_index[peer] - 1
        prev_term = None
        entries = [] if heartbeat else self.log[self.next_index[peer]:]
        # Simulate success with 80% reliability
        success = self.rng.random() < 0.8
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
            f"[{self.node_id}] AppendEntries -> {peer} success={success} hb={heartbeat} prev=({prev_index},{prev_term}) send={len(entries)} next_index={self.next_index[peer]}"
        )
        return success

    def xǁRaftNodeǁ_append_entries_rpc__mutmut_6(self, peer: str, heartbeat: bool = False) -> bool:
        prev_index = self.next_index[peer] - 1
        prev_term = self.log[prev_index].term if prev_index <= len(self.log) else 0
        entries = [] if heartbeat else self.log[self.next_index[peer]:]
        # Simulate success with 80% reliability
        success = self.rng.random() < 0.8
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
            f"[{self.node_id}] AppendEntries -> {peer} success={success} hb={heartbeat} prev=({prev_index},{prev_term}) send={len(entries)} next_index={self.next_index[peer]}"
        )
        return success

    def xǁRaftNodeǁ_append_entries_rpc__mutmut_7(self, peer: str, heartbeat: bool = False) -> bool:
        prev_index = self.next_index[peer] - 1
        prev_term = self.log[prev_index].term if prev_index < len(self.log) else 1
        entries = [] if heartbeat else self.log[self.next_index[peer]:]
        # Simulate success with 80% reliability
        success = self.rng.random() < 0.8
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
            f"[{self.node_id}] AppendEntries -> {peer} success={success} hb={heartbeat} prev=({prev_index},{prev_term}) send={len(entries)} next_index={self.next_index[peer]}"
        )
        return success

    def xǁRaftNodeǁ_append_entries_rpc__mutmut_8(self, peer: str, heartbeat: bool = False) -> bool:
        prev_index = self.next_index[peer] - 1
        prev_term = self.log[prev_index].term if prev_index < len(self.log) else 0
        entries = None
        # Simulate success with 80% reliability
        success = self.rng.random() < 0.8
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
            f"[{self.node_id}] AppendEntries -> {peer} success={success} hb={heartbeat} prev=({prev_index},{prev_term}) send={len(entries)} next_index={self.next_index[peer]}"
        )
        return success

    def xǁRaftNodeǁ_append_entries_rpc__mutmut_9(self, peer: str, heartbeat: bool = False) -> bool:
        prev_index = self.next_index[peer] - 1
        prev_term = self.log[prev_index].term if prev_index < len(self.log) else 0
        entries = [] if heartbeat else self.log[self.next_index[peer]:]
        # Simulate success with 80% reliability
        success = None
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
            f"[{self.node_id}] AppendEntries -> {peer} success={success} hb={heartbeat} prev=({prev_index},{prev_term}) send={len(entries)} next_index={self.next_index[peer]}"
        )
        return success

    def xǁRaftNodeǁ_append_entries_rpc__mutmut_10(self, peer: str, heartbeat: bool = False) -> bool:
        prev_index = self.next_index[peer] - 1
        prev_term = self.log[prev_index].term if prev_index < len(self.log) else 0
        entries = [] if heartbeat else self.log[self.next_index[peer]:]
        # Simulate success with 80% reliability
        success = self.rng.random() <= 0.8
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
            f"[{self.node_id}] AppendEntries -> {peer} success={success} hb={heartbeat} prev=({prev_index},{prev_term}) send={len(entries)} next_index={self.next_index[peer]}"
        )
        return success

    def xǁRaftNodeǁ_append_entries_rpc__mutmut_11(self, peer: str, heartbeat: bool = False) -> bool:
        prev_index = self.next_index[peer] - 1
        prev_term = self.log[prev_index].term if prev_index < len(self.log) else 0
        entries = [] if heartbeat else self.log[self.next_index[peer]:]
        # Simulate success with 80% reliability
        success = self.rng.random() < 1.8
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
            f"[{self.node_id}] AppendEntries -> {peer} success={success} hb={heartbeat} prev=({prev_index},{prev_term}) send={len(entries)} next_index={self.next_index[peer]}"
        )
        return success

    def xǁRaftNodeǁ_append_entries_rpc__mutmut_12(self, peer: str, heartbeat: bool = False) -> bool:
        prev_index = self.next_index[peer] - 1
        prev_term = self.log[prev_index].term if prev_index < len(self.log) else 0
        entries = [] if heartbeat else self.log[self.next_index[peer]:]
        # Simulate success with 80% reliability
        success = self.rng.random() < 0.8
        if success:
            if entries:
                self.match_index[peer] = None
                self.next_index[peer] = self.match_index[peer] + 1
            else:  # heartbeat keeps alignment
                self.match_index[peer] = max(self.match_index[peer], prev_index)
        else:
            # Decrement next_index to retry previous
            self.next_index[peer] = max(1, self.next_index[peer] - 1)
        logger.debug(
            f"[{self.node_id}] AppendEntries -> {peer} success={success} hb={heartbeat} prev=({prev_index},{prev_term}) send={len(entries)} next_index={self.next_index[peer]}"
        )
        return success

    def xǁRaftNodeǁ_append_entries_rpc__mutmut_13(self, peer: str, heartbeat: bool = False) -> bool:
        prev_index = self.next_index[peer] - 1
        prev_term = self.log[prev_index].term if prev_index < len(self.log) else 0
        entries = [] if heartbeat else self.log[self.next_index[peer]:]
        # Simulate success with 80% reliability
        success = self.rng.random() < 0.8
        if success:
            if entries:
                self.match_index[peer] = entries[+1].index
                self.next_index[peer] = self.match_index[peer] + 1
            else:  # heartbeat keeps alignment
                self.match_index[peer] = max(self.match_index[peer], prev_index)
        else:
            # Decrement next_index to retry previous
            self.next_index[peer] = max(1, self.next_index[peer] - 1)
        logger.debug(
            f"[{self.node_id}] AppendEntries -> {peer} success={success} hb={heartbeat} prev=({prev_index},{prev_term}) send={len(entries)} next_index={self.next_index[peer]}"
        )
        return success

    def xǁRaftNodeǁ_append_entries_rpc__mutmut_14(self, peer: str, heartbeat: bool = False) -> bool:
        prev_index = self.next_index[peer] - 1
        prev_term = self.log[prev_index].term if prev_index < len(self.log) else 0
        entries = [] if heartbeat else self.log[self.next_index[peer]:]
        # Simulate success with 80% reliability
        success = self.rng.random() < 0.8
        if success:
            if entries:
                self.match_index[peer] = entries[-2].index
                self.next_index[peer] = self.match_index[peer] + 1
            else:  # heartbeat keeps alignment
                self.match_index[peer] = max(self.match_index[peer], prev_index)
        else:
            # Decrement next_index to retry previous
            self.next_index[peer] = max(1, self.next_index[peer] - 1)
        logger.debug(
            f"[{self.node_id}] AppendEntries -> {peer} success={success} hb={heartbeat} prev=({prev_index},{prev_term}) send={len(entries)} next_index={self.next_index[peer]}"
        )
        return success

    def xǁRaftNodeǁ_append_entries_rpc__mutmut_15(self, peer: str, heartbeat: bool = False) -> bool:
        prev_index = self.next_index[peer] - 1
        prev_term = self.log[prev_index].term if prev_index < len(self.log) else 0
        entries = [] if heartbeat else self.log[self.next_index[peer]:]
        # Simulate success with 80% reliability
        success = self.rng.random() < 0.8
        if success:
            if entries:
                self.match_index[peer] = entries[-1].index
                self.next_index[peer] = None
            else:  # heartbeat keeps alignment
                self.match_index[peer] = max(self.match_index[peer], prev_index)
        else:
            # Decrement next_index to retry previous
            self.next_index[peer] = max(1, self.next_index[peer] - 1)
        logger.debug(
            f"[{self.node_id}] AppendEntries -> {peer} success={success} hb={heartbeat} prev=({prev_index},{prev_term}) send={len(entries)} next_index={self.next_index[peer]}"
        )
        return success

    def xǁRaftNodeǁ_append_entries_rpc__mutmut_16(self, peer: str, heartbeat: bool = False) -> bool:
        prev_index = self.next_index[peer] - 1
        prev_term = self.log[prev_index].term if prev_index < len(self.log) else 0
        entries = [] if heartbeat else self.log[self.next_index[peer]:]
        # Simulate success with 80% reliability
        success = self.rng.random() < 0.8
        if success:
            if entries:
                self.match_index[peer] = entries[-1].index
                self.next_index[peer] = self.match_index[peer] - 1
            else:  # heartbeat keeps alignment
                self.match_index[peer] = max(self.match_index[peer], prev_index)
        else:
            # Decrement next_index to retry previous
            self.next_index[peer] = max(1, self.next_index[peer] - 1)
        logger.debug(
            f"[{self.node_id}] AppendEntries -> {peer} success={success} hb={heartbeat} prev=({prev_index},{prev_term}) send={len(entries)} next_index={self.next_index[peer]}"
        )
        return success

    def xǁRaftNodeǁ_append_entries_rpc__mutmut_17(self, peer: str, heartbeat: bool = False) -> bool:
        prev_index = self.next_index[peer] - 1
        prev_term = self.log[prev_index].term if prev_index < len(self.log) else 0
        entries = [] if heartbeat else self.log[self.next_index[peer]:]
        # Simulate success with 80% reliability
        success = self.rng.random() < 0.8
        if success:
            if entries:
                self.match_index[peer] = entries[-1].index
                self.next_index[peer] = self.match_index[peer] + 2
            else:  # heartbeat keeps alignment
                self.match_index[peer] = max(self.match_index[peer], prev_index)
        else:
            # Decrement next_index to retry previous
            self.next_index[peer] = max(1, self.next_index[peer] - 1)
        logger.debug(
            f"[{self.node_id}] AppendEntries -> {peer} success={success} hb={heartbeat} prev=({prev_index},{prev_term}) send={len(entries)} next_index={self.next_index[peer]}"
        )
        return success

    def xǁRaftNodeǁ_append_entries_rpc__mutmut_18(self, peer: str, heartbeat: bool = False) -> bool:
        prev_index = self.next_index[peer] - 1
        prev_term = self.log[prev_index].term if prev_index < len(self.log) else 0
        entries = [] if heartbeat else self.log[self.next_index[peer]:]
        # Simulate success with 80% reliability
        success = self.rng.random() < 0.8
        if success:
            if entries:
                self.match_index[peer] = entries[-1].index
                self.next_index[peer] = self.match_index[peer] + 1
            else:  # heartbeat keeps alignment
                self.match_index[peer] = None
        else:
            # Decrement next_index to retry previous
            self.next_index[peer] = max(1, self.next_index[peer] - 1)
        logger.debug(
            f"[{self.node_id}] AppendEntries -> {peer} success={success} hb={heartbeat} prev=({prev_index},{prev_term}) send={len(entries)} next_index={self.next_index[peer]}"
        )
        return success

    def xǁRaftNodeǁ_append_entries_rpc__mutmut_19(self, peer: str, heartbeat: bool = False) -> bool:
        prev_index = self.next_index[peer] - 1
        prev_term = self.log[prev_index].term if prev_index < len(self.log) else 0
        entries = [] if heartbeat else self.log[self.next_index[peer]:]
        # Simulate success with 80% reliability
        success = self.rng.random() < 0.8
        if success:
            if entries:
                self.match_index[peer] = entries[-1].index
                self.next_index[peer] = self.match_index[peer] + 1
            else:  # heartbeat keeps alignment
                self.match_index[peer] = max(None, prev_index)
        else:
            # Decrement next_index to retry previous
            self.next_index[peer] = max(1, self.next_index[peer] - 1)
        logger.debug(
            f"[{self.node_id}] AppendEntries -> {peer} success={success} hb={heartbeat} prev=({prev_index},{prev_term}) send={len(entries)} next_index={self.next_index[peer]}"
        )
        return success

    def xǁRaftNodeǁ_append_entries_rpc__mutmut_20(self, peer: str, heartbeat: bool = False) -> bool:
        prev_index = self.next_index[peer] - 1
        prev_term = self.log[prev_index].term if prev_index < len(self.log) else 0
        entries = [] if heartbeat else self.log[self.next_index[peer]:]
        # Simulate success with 80% reliability
        success = self.rng.random() < 0.8
        if success:
            if entries:
                self.match_index[peer] = entries[-1].index
                self.next_index[peer] = self.match_index[peer] + 1
            else:  # heartbeat keeps alignment
                self.match_index[peer] = max(self.match_index[peer], None)
        else:
            # Decrement next_index to retry previous
            self.next_index[peer] = max(1, self.next_index[peer] - 1)
        logger.debug(
            f"[{self.node_id}] AppendEntries -> {peer} success={success} hb={heartbeat} prev=({prev_index},{prev_term}) send={len(entries)} next_index={self.next_index[peer]}"
        )
        return success

    def xǁRaftNodeǁ_append_entries_rpc__mutmut_21(self, peer: str, heartbeat: bool = False) -> bool:
        prev_index = self.next_index[peer] - 1
        prev_term = self.log[prev_index].term if prev_index < len(self.log) else 0
        entries = [] if heartbeat else self.log[self.next_index[peer]:]
        # Simulate success with 80% reliability
        success = self.rng.random() < 0.8
        if success:
            if entries:
                self.match_index[peer] = entries[-1].index
                self.next_index[peer] = self.match_index[peer] + 1
            else:  # heartbeat keeps alignment
                self.match_index[peer] = max(prev_index)
        else:
            # Decrement next_index to retry previous
            self.next_index[peer] = max(1, self.next_index[peer] - 1)
        logger.debug(
            f"[{self.node_id}] AppendEntries -> {peer} success={success} hb={heartbeat} prev=({prev_index},{prev_term}) send={len(entries)} next_index={self.next_index[peer]}"
        )
        return success

    def xǁRaftNodeǁ_append_entries_rpc__mutmut_22(self, peer: str, heartbeat: bool = False) -> bool:
        prev_index = self.next_index[peer] - 1
        prev_term = self.log[prev_index].term if prev_index < len(self.log) else 0
        entries = [] if heartbeat else self.log[self.next_index[peer]:]
        # Simulate success with 80% reliability
        success = self.rng.random() < 0.8
        if success:
            if entries:
                self.match_index[peer] = entries[-1].index
                self.next_index[peer] = self.match_index[peer] + 1
            else:  # heartbeat keeps alignment
                self.match_index[peer] = max(self.match_index[peer], )
        else:
            # Decrement next_index to retry previous
            self.next_index[peer] = max(1, self.next_index[peer] - 1)
        logger.debug(
            f"[{self.node_id}] AppendEntries -> {peer} success={success} hb={heartbeat} prev=({prev_index},{prev_term}) send={len(entries)} next_index={self.next_index[peer]}"
        )
        return success

    def xǁRaftNodeǁ_append_entries_rpc__mutmut_23(self, peer: str, heartbeat: bool = False) -> bool:
        prev_index = self.next_index[peer] - 1
        prev_term = self.log[prev_index].term if prev_index < len(self.log) else 0
        entries = [] if heartbeat else self.log[self.next_index[peer]:]
        # Simulate success with 80% reliability
        success = self.rng.random() < 0.8
        if success:
            if entries:
                self.match_index[peer] = entries[-1].index
                self.next_index[peer] = self.match_index[peer] + 1
            else:  # heartbeat keeps alignment
                self.match_index[peer] = max(self.match_index[peer], prev_index)
        else:
            # Decrement next_index to retry previous
            self.next_index[peer] = None
        logger.debug(
            f"[{self.node_id}] AppendEntries -> {peer} success={success} hb={heartbeat} prev=({prev_index},{prev_term}) send={len(entries)} next_index={self.next_index[peer]}"
        )
        return success

    def xǁRaftNodeǁ_append_entries_rpc__mutmut_24(self, peer: str, heartbeat: bool = False) -> bool:
        prev_index = self.next_index[peer] - 1
        prev_term = self.log[prev_index].term if prev_index < len(self.log) else 0
        entries = [] if heartbeat else self.log[self.next_index[peer]:]
        # Simulate success with 80% reliability
        success = self.rng.random() < 0.8
        if success:
            if entries:
                self.match_index[peer] = entries[-1].index
                self.next_index[peer] = self.match_index[peer] + 1
            else:  # heartbeat keeps alignment
                self.match_index[peer] = max(self.match_index[peer], prev_index)
        else:
            # Decrement next_index to retry previous
            self.next_index[peer] = max(None, self.next_index[peer] - 1)
        logger.debug(
            f"[{self.node_id}] AppendEntries -> {peer} success={success} hb={heartbeat} prev=({prev_index},{prev_term}) send={len(entries)} next_index={self.next_index[peer]}"
        )
        return success

    def xǁRaftNodeǁ_append_entries_rpc__mutmut_25(self, peer: str, heartbeat: bool = False) -> bool:
        prev_index = self.next_index[peer] - 1
        prev_term = self.log[prev_index].term if prev_index < len(self.log) else 0
        entries = [] if heartbeat else self.log[self.next_index[peer]:]
        # Simulate success with 80% reliability
        success = self.rng.random() < 0.8
        if success:
            if entries:
                self.match_index[peer] = entries[-1].index
                self.next_index[peer] = self.match_index[peer] + 1
            else:  # heartbeat keeps alignment
                self.match_index[peer] = max(self.match_index[peer], prev_index)
        else:
            # Decrement next_index to retry previous
            self.next_index[peer] = max(1, None)
        logger.debug(
            f"[{self.node_id}] AppendEntries -> {peer} success={success} hb={heartbeat} prev=({prev_index},{prev_term}) send={len(entries)} next_index={self.next_index[peer]}"
        )
        return success

    def xǁRaftNodeǁ_append_entries_rpc__mutmut_26(self, peer: str, heartbeat: bool = False) -> bool:
        prev_index = self.next_index[peer] - 1
        prev_term = self.log[prev_index].term if prev_index < len(self.log) else 0
        entries = [] if heartbeat else self.log[self.next_index[peer]:]
        # Simulate success with 80% reliability
        success = self.rng.random() < 0.8
        if success:
            if entries:
                self.match_index[peer] = entries[-1].index
                self.next_index[peer] = self.match_index[peer] + 1
            else:  # heartbeat keeps alignment
                self.match_index[peer] = max(self.match_index[peer], prev_index)
        else:
            # Decrement next_index to retry previous
            self.next_index[peer] = max(self.next_index[peer] - 1)
        logger.debug(
            f"[{self.node_id}] AppendEntries -> {peer} success={success} hb={heartbeat} prev=({prev_index},{prev_term}) send={len(entries)} next_index={self.next_index[peer]}"
        )
        return success

    def xǁRaftNodeǁ_append_entries_rpc__mutmut_27(self, peer: str, heartbeat: bool = False) -> bool:
        prev_index = self.next_index[peer] - 1
        prev_term = self.log[prev_index].term if prev_index < len(self.log) else 0
        entries = [] if heartbeat else self.log[self.next_index[peer]:]
        # Simulate success with 80% reliability
        success = self.rng.random() < 0.8
        if success:
            if entries:
                self.match_index[peer] = entries[-1].index
                self.next_index[peer] = self.match_index[peer] + 1
            else:  # heartbeat keeps alignment
                self.match_index[peer] = max(self.match_index[peer], prev_index)
        else:
            # Decrement next_index to retry previous
            self.next_index[peer] = max(1, )
        logger.debug(
            f"[{self.node_id}] AppendEntries -> {peer} success={success} hb={heartbeat} prev=({prev_index},{prev_term}) send={len(entries)} next_index={self.next_index[peer]}"
        )
        return success

    def xǁRaftNodeǁ_append_entries_rpc__mutmut_28(self, peer: str, heartbeat: bool = False) -> bool:
        prev_index = self.next_index[peer] - 1
        prev_term = self.log[prev_index].term if prev_index < len(self.log) else 0
        entries = [] if heartbeat else self.log[self.next_index[peer]:]
        # Simulate success with 80% reliability
        success = self.rng.random() < 0.8
        if success:
            if entries:
                self.match_index[peer] = entries[-1].index
                self.next_index[peer] = self.match_index[peer] + 1
            else:  # heartbeat keeps alignment
                self.match_index[peer] = max(self.match_index[peer], prev_index)
        else:
            # Decrement next_index to retry previous
            self.next_index[peer] = max(2, self.next_index[peer] - 1)
        logger.debug(
            f"[{self.node_id}] AppendEntries -> {peer} success={success} hb={heartbeat} prev=({prev_index},{prev_term}) send={len(entries)} next_index={self.next_index[peer]}"
        )
        return success

    def xǁRaftNodeǁ_append_entries_rpc__mutmut_29(self, peer: str, heartbeat: bool = False) -> bool:
        prev_index = self.next_index[peer] - 1
        prev_term = self.log[prev_index].term if prev_index < len(self.log) else 0
        entries = [] if heartbeat else self.log[self.next_index[peer]:]
        # Simulate success with 80% reliability
        success = self.rng.random() < 0.8
        if success:
            if entries:
                self.match_index[peer] = entries[-1].index
                self.next_index[peer] = self.match_index[peer] + 1
            else:  # heartbeat keeps alignment
                self.match_index[peer] = max(self.match_index[peer], prev_index)
        else:
            # Decrement next_index to retry previous
            self.next_index[peer] = max(1, self.next_index[peer] + 1)
        logger.debug(
            f"[{self.node_id}] AppendEntries -> {peer} success={success} hb={heartbeat} prev=({prev_index},{prev_term}) send={len(entries)} next_index={self.next_index[peer]}"
        )
        return success

    def xǁRaftNodeǁ_append_entries_rpc__mutmut_30(self, peer: str, heartbeat: bool = False) -> bool:
        prev_index = self.next_index[peer] - 1
        prev_term = self.log[prev_index].term if prev_index < len(self.log) else 0
        entries = [] if heartbeat else self.log[self.next_index[peer]:]
        # Simulate success with 80% reliability
        success = self.rng.random() < 0.8
        if success:
            if entries:
                self.match_index[peer] = entries[-1].index
                self.next_index[peer] = self.match_index[peer] + 1
            else:  # heartbeat keeps alignment
                self.match_index[peer] = max(self.match_index[peer], prev_index)
        else:
            # Decrement next_index to retry previous
            self.next_index[peer] = max(1, self.next_index[peer] - 2)
        logger.debug(
            f"[{self.node_id}] AppendEntries -> {peer} success={success} hb={heartbeat} prev=({prev_index},{prev_term}) send={len(entries)} next_index={self.next_index[peer]}"
        )
        return success

    def xǁRaftNodeǁ_append_entries_rpc__mutmut_31(self, peer: str, heartbeat: bool = False) -> bool:
        prev_index = self.next_index[peer] - 1
        prev_term = self.log[prev_index].term if prev_index < len(self.log) else 0
        entries = [] if heartbeat else self.log[self.next_index[peer]:]
        # Simulate success with 80% reliability
        success = self.rng.random() < 0.8
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
            None
        )
        return success
    
    xǁRaftNodeǁ_append_entries_rpc__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁRaftNodeǁ_append_entries_rpc__mutmut_1': xǁRaftNodeǁ_append_entries_rpc__mutmut_1, 
        'xǁRaftNodeǁ_append_entries_rpc__mutmut_2': xǁRaftNodeǁ_append_entries_rpc__mutmut_2, 
        'xǁRaftNodeǁ_append_entries_rpc__mutmut_3': xǁRaftNodeǁ_append_entries_rpc__mutmut_3, 
        'xǁRaftNodeǁ_append_entries_rpc__mutmut_4': xǁRaftNodeǁ_append_entries_rpc__mutmut_4, 
        'xǁRaftNodeǁ_append_entries_rpc__mutmut_5': xǁRaftNodeǁ_append_entries_rpc__mutmut_5, 
        'xǁRaftNodeǁ_append_entries_rpc__mutmut_6': xǁRaftNodeǁ_append_entries_rpc__mutmut_6, 
        'xǁRaftNodeǁ_append_entries_rpc__mutmut_7': xǁRaftNodeǁ_append_entries_rpc__mutmut_7, 
        'xǁRaftNodeǁ_append_entries_rpc__mutmut_8': xǁRaftNodeǁ_append_entries_rpc__mutmut_8, 
        'xǁRaftNodeǁ_append_entries_rpc__mutmut_9': xǁRaftNodeǁ_append_entries_rpc__mutmut_9, 
        'xǁRaftNodeǁ_append_entries_rpc__mutmut_10': xǁRaftNodeǁ_append_entries_rpc__mutmut_10, 
        'xǁRaftNodeǁ_append_entries_rpc__mutmut_11': xǁRaftNodeǁ_append_entries_rpc__mutmut_11, 
        'xǁRaftNodeǁ_append_entries_rpc__mutmut_12': xǁRaftNodeǁ_append_entries_rpc__mutmut_12, 
        'xǁRaftNodeǁ_append_entries_rpc__mutmut_13': xǁRaftNodeǁ_append_entries_rpc__mutmut_13, 
        'xǁRaftNodeǁ_append_entries_rpc__mutmut_14': xǁRaftNodeǁ_append_entries_rpc__mutmut_14, 
        'xǁRaftNodeǁ_append_entries_rpc__mutmut_15': xǁRaftNodeǁ_append_entries_rpc__mutmut_15, 
        'xǁRaftNodeǁ_append_entries_rpc__mutmut_16': xǁRaftNodeǁ_append_entries_rpc__mutmut_16, 
        'xǁRaftNodeǁ_append_entries_rpc__mutmut_17': xǁRaftNodeǁ_append_entries_rpc__mutmut_17, 
        'xǁRaftNodeǁ_append_entries_rpc__mutmut_18': xǁRaftNodeǁ_append_entries_rpc__mutmut_18, 
        'xǁRaftNodeǁ_append_entries_rpc__mutmut_19': xǁRaftNodeǁ_append_entries_rpc__mutmut_19, 
        'xǁRaftNodeǁ_append_entries_rpc__mutmut_20': xǁRaftNodeǁ_append_entries_rpc__mutmut_20, 
        'xǁRaftNodeǁ_append_entries_rpc__mutmut_21': xǁRaftNodeǁ_append_entries_rpc__mutmut_21, 
        'xǁRaftNodeǁ_append_entries_rpc__mutmut_22': xǁRaftNodeǁ_append_entries_rpc__mutmut_22, 
        'xǁRaftNodeǁ_append_entries_rpc__mutmut_23': xǁRaftNodeǁ_append_entries_rpc__mutmut_23, 
        'xǁRaftNodeǁ_append_entries_rpc__mutmut_24': xǁRaftNodeǁ_append_entries_rpc__mutmut_24, 
        'xǁRaftNodeǁ_append_entries_rpc__mutmut_25': xǁRaftNodeǁ_append_entries_rpc__mutmut_25, 
        'xǁRaftNodeǁ_append_entries_rpc__mutmut_26': xǁRaftNodeǁ_append_entries_rpc__mutmut_26, 
        'xǁRaftNodeǁ_append_entries_rpc__mutmut_27': xǁRaftNodeǁ_append_entries_rpc__mutmut_27, 
        'xǁRaftNodeǁ_append_entries_rpc__mutmut_28': xǁRaftNodeǁ_append_entries_rpc__mutmut_28, 
        'xǁRaftNodeǁ_append_entries_rpc__mutmut_29': xǁRaftNodeǁ_append_entries_rpc__mutmut_29, 
        'xǁRaftNodeǁ_append_entries_rpc__mutmut_30': xǁRaftNodeǁ_append_entries_rpc__mutmut_30, 
        'xǁRaftNodeǁ_append_entries_rpc__mutmut_31': xǁRaftNodeǁ_append_entries_rpc__mutmut_31
    }
    
    def _append_entries_rpc(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁRaftNodeǁ_append_entries_rpc__mutmut_orig"), object.__getattribute__(self, "xǁRaftNodeǁ_append_entries_rpc__mutmut_mutants"), args, kwargs, self)
        return result 
    
    _append_entries_rpc.__signature__ = _mutmut_signature(xǁRaftNodeǁ_append_entries_rpc__mutmut_orig)
    xǁRaftNodeǁ_append_entries_rpc__mutmut_orig.__name__ = 'xǁRaftNodeǁ_append_entries_rpc'

    def xǁRaftNodeǁ_advance_commit_index__mutmut_orig(self):
        if self.state != RaftState.LEADER:
            return
        # Find highest N > commit_index such that a majority have match_index >= N and log[N].term == current_term
        for N in range(len(self.log) - 1, self.commit_index, -1):
            count = 1  # leader itself
            for peer in self.peers:
                if self.match_index[peer] >= N:
                    count += 1
            if count > len(self.peers) // 2 and self.log[N].term == self.current_term:
                old_commit = self.commit_index
                self.commit_index = N
                logger.debug(f"[{self.node_id}] Commit index advanced {old_commit} -> {self.commit_index}")
                self._apply_entries(old_commit)
                break

    def xǁRaftNodeǁ_advance_commit_index__mutmut_1(self):
        if self.state == RaftState.LEADER:
            return
        # Find highest N > commit_index such that a majority have match_index >= N and log[N].term == current_term
        for N in range(len(self.log) - 1, self.commit_index, -1):
            count = 1  # leader itself
            for peer in self.peers:
                if self.match_index[peer] >= N:
                    count += 1
            if count > len(self.peers) // 2 and self.log[N].term == self.current_term:
                old_commit = self.commit_index
                self.commit_index = N
                logger.debug(f"[{self.node_id}] Commit index advanced {old_commit} -> {self.commit_index}")
                self._apply_entries(old_commit)
                break

    def xǁRaftNodeǁ_advance_commit_index__mutmut_2(self):
        if self.state != RaftState.LEADER:
            return
        # Find highest N > commit_index such that a majority have match_index >= N and log[N].term == current_term
        for N in range(None, self.commit_index, -1):
            count = 1  # leader itself
            for peer in self.peers:
                if self.match_index[peer] >= N:
                    count += 1
            if count > len(self.peers) // 2 and self.log[N].term == self.current_term:
                old_commit = self.commit_index
                self.commit_index = N
                logger.debug(f"[{self.node_id}] Commit index advanced {old_commit} -> {self.commit_index}")
                self._apply_entries(old_commit)
                break

    def xǁRaftNodeǁ_advance_commit_index__mutmut_3(self):
        if self.state != RaftState.LEADER:
            return
        # Find highest N > commit_index such that a majority have match_index >= N and log[N].term == current_term
        for N in range(len(self.log) - 1, None, -1):
            count = 1  # leader itself
            for peer in self.peers:
                if self.match_index[peer] >= N:
                    count += 1
            if count > len(self.peers) // 2 and self.log[N].term == self.current_term:
                old_commit = self.commit_index
                self.commit_index = N
                logger.debug(f"[{self.node_id}] Commit index advanced {old_commit} -> {self.commit_index}")
                self._apply_entries(old_commit)
                break

    def xǁRaftNodeǁ_advance_commit_index__mutmut_4(self):
        if self.state != RaftState.LEADER:
            return
        # Find highest N > commit_index such that a majority have match_index >= N and log[N].term == current_term
        for N in range(len(self.log) - 1, self.commit_index, None):
            count = 1  # leader itself
            for peer in self.peers:
                if self.match_index[peer] >= N:
                    count += 1
            if count > len(self.peers) // 2 and self.log[N].term == self.current_term:
                old_commit = self.commit_index
                self.commit_index = N
                logger.debug(f"[{self.node_id}] Commit index advanced {old_commit} -> {self.commit_index}")
                self._apply_entries(old_commit)
                break

    def xǁRaftNodeǁ_advance_commit_index__mutmut_5(self):
        if self.state != RaftState.LEADER:
            return
        # Find highest N > commit_index such that a majority have match_index >= N and log[N].term == current_term
        for N in range(self.commit_index, -1):
            count = 1  # leader itself
            for peer in self.peers:
                if self.match_index[peer] >= N:
                    count += 1
            if count > len(self.peers) // 2 and self.log[N].term == self.current_term:
                old_commit = self.commit_index
                self.commit_index = N
                logger.debug(f"[{self.node_id}] Commit index advanced {old_commit} -> {self.commit_index}")
                self._apply_entries(old_commit)
                break

    def xǁRaftNodeǁ_advance_commit_index__mutmut_6(self):
        if self.state != RaftState.LEADER:
            return
        # Find highest N > commit_index such that a majority have match_index >= N and log[N].term == current_term
        for N in range(len(self.log) - 1, -1):
            count = 1  # leader itself
            for peer in self.peers:
                if self.match_index[peer] >= N:
                    count += 1
            if count > len(self.peers) // 2 and self.log[N].term == self.current_term:
                old_commit = self.commit_index
                self.commit_index = N
                logger.debug(f"[{self.node_id}] Commit index advanced {old_commit} -> {self.commit_index}")
                self._apply_entries(old_commit)
                break

    def xǁRaftNodeǁ_advance_commit_index__mutmut_7(self):
        if self.state != RaftState.LEADER:
            return
        # Find highest N > commit_index such that a majority have match_index >= N and log[N].term == current_term
        for N in range(len(self.log) - 1, self.commit_index, ):
            count = 1  # leader itself
            for peer in self.peers:
                if self.match_index[peer] >= N:
                    count += 1
            if count > len(self.peers) // 2 and self.log[N].term == self.current_term:
                old_commit = self.commit_index
                self.commit_index = N
                logger.debug(f"[{self.node_id}] Commit index advanced {old_commit} -> {self.commit_index}")
                self._apply_entries(old_commit)
                break

    def xǁRaftNodeǁ_advance_commit_index__mutmut_8(self):
        if self.state != RaftState.LEADER:
            return
        # Find highest N > commit_index such that a majority have match_index >= N and log[N].term == current_term
        for N in range(len(self.log) + 1, self.commit_index, -1):
            count = 1  # leader itself
            for peer in self.peers:
                if self.match_index[peer] >= N:
                    count += 1
            if count > len(self.peers) // 2 and self.log[N].term == self.current_term:
                old_commit = self.commit_index
                self.commit_index = N
                logger.debug(f"[{self.node_id}] Commit index advanced {old_commit} -> {self.commit_index}")
                self._apply_entries(old_commit)
                break

    def xǁRaftNodeǁ_advance_commit_index__mutmut_9(self):
        if self.state != RaftState.LEADER:
            return
        # Find highest N > commit_index such that a majority have match_index >= N and log[N].term == current_term
        for N in range(len(self.log) - 2, self.commit_index, -1):
            count = 1  # leader itself
            for peer in self.peers:
                if self.match_index[peer] >= N:
                    count += 1
            if count > len(self.peers) // 2 and self.log[N].term == self.current_term:
                old_commit = self.commit_index
                self.commit_index = N
                logger.debug(f"[{self.node_id}] Commit index advanced {old_commit} -> {self.commit_index}")
                self._apply_entries(old_commit)
                break

    def xǁRaftNodeǁ_advance_commit_index__mutmut_10(self):
        if self.state != RaftState.LEADER:
            return
        # Find highest N > commit_index such that a majority have match_index >= N and log[N].term == current_term
        for N in range(len(self.log) - 1, self.commit_index, +1):
            count = 1  # leader itself
            for peer in self.peers:
                if self.match_index[peer] >= N:
                    count += 1
            if count > len(self.peers) // 2 and self.log[N].term == self.current_term:
                old_commit = self.commit_index
                self.commit_index = N
                logger.debug(f"[{self.node_id}] Commit index advanced {old_commit} -> {self.commit_index}")
                self._apply_entries(old_commit)
                break

    def xǁRaftNodeǁ_advance_commit_index__mutmut_11(self):
        if self.state != RaftState.LEADER:
            return
        # Find highest N > commit_index such that a majority have match_index >= N and log[N].term == current_term
        for N in range(len(self.log) - 1, self.commit_index, -2):
            count = 1  # leader itself
            for peer in self.peers:
                if self.match_index[peer] >= N:
                    count += 1
            if count > len(self.peers) // 2 and self.log[N].term == self.current_term:
                old_commit = self.commit_index
                self.commit_index = N
                logger.debug(f"[{self.node_id}] Commit index advanced {old_commit} -> {self.commit_index}")
                self._apply_entries(old_commit)
                break

    def xǁRaftNodeǁ_advance_commit_index__mutmut_12(self):
        if self.state != RaftState.LEADER:
            return
        # Find highest N > commit_index such that a majority have match_index >= N and log[N].term == current_term
        for N in range(len(self.log) - 1, self.commit_index, -1):
            count = None  # leader itself
            for peer in self.peers:
                if self.match_index[peer] >= N:
                    count += 1
            if count > len(self.peers) // 2 and self.log[N].term == self.current_term:
                old_commit = self.commit_index
                self.commit_index = N
                logger.debug(f"[{self.node_id}] Commit index advanced {old_commit} -> {self.commit_index}")
                self._apply_entries(old_commit)
                break

    def xǁRaftNodeǁ_advance_commit_index__mutmut_13(self):
        if self.state != RaftState.LEADER:
            return
        # Find highest N > commit_index such that a majority have match_index >= N and log[N].term == current_term
        for N in range(len(self.log) - 1, self.commit_index, -1):
            count = 2  # leader itself
            for peer in self.peers:
                if self.match_index[peer] >= N:
                    count += 1
            if count > len(self.peers) // 2 and self.log[N].term == self.current_term:
                old_commit = self.commit_index
                self.commit_index = N
                logger.debug(f"[{self.node_id}] Commit index advanced {old_commit} -> {self.commit_index}")
                self._apply_entries(old_commit)
                break

    def xǁRaftNodeǁ_advance_commit_index__mutmut_14(self):
        if self.state != RaftState.LEADER:
            return
        # Find highest N > commit_index such that a majority have match_index >= N and log[N].term == current_term
        for N in range(len(self.log) - 1, self.commit_index, -1):
            count = 1  # leader itself
            for peer in self.peers:
                if self.match_index[peer] > N:
                    count += 1
            if count > len(self.peers) // 2 and self.log[N].term == self.current_term:
                old_commit = self.commit_index
                self.commit_index = N
                logger.debug(f"[{self.node_id}] Commit index advanced {old_commit} -> {self.commit_index}")
                self._apply_entries(old_commit)
                break

    def xǁRaftNodeǁ_advance_commit_index__mutmut_15(self):
        if self.state != RaftState.LEADER:
            return
        # Find highest N > commit_index such that a majority have match_index >= N and log[N].term == current_term
        for N in range(len(self.log) - 1, self.commit_index, -1):
            count = 1  # leader itself
            for peer in self.peers:
                if self.match_index[peer] >= N:
                    count = 1
            if count > len(self.peers) // 2 and self.log[N].term == self.current_term:
                old_commit = self.commit_index
                self.commit_index = N
                logger.debug(f"[{self.node_id}] Commit index advanced {old_commit} -> {self.commit_index}")
                self._apply_entries(old_commit)
                break

    def xǁRaftNodeǁ_advance_commit_index__mutmut_16(self):
        if self.state != RaftState.LEADER:
            return
        # Find highest N > commit_index such that a majority have match_index >= N and log[N].term == current_term
        for N in range(len(self.log) - 1, self.commit_index, -1):
            count = 1  # leader itself
            for peer in self.peers:
                if self.match_index[peer] >= N:
                    count -= 1
            if count > len(self.peers) // 2 and self.log[N].term == self.current_term:
                old_commit = self.commit_index
                self.commit_index = N
                logger.debug(f"[{self.node_id}] Commit index advanced {old_commit} -> {self.commit_index}")
                self._apply_entries(old_commit)
                break

    def xǁRaftNodeǁ_advance_commit_index__mutmut_17(self):
        if self.state != RaftState.LEADER:
            return
        # Find highest N > commit_index such that a majority have match_index >= N and log[N].term == current_term
        for N in range(len(self.log) - 1, self.commit_index, -1):
            count = 1  # leader itself
            for peer in self.peers:
                if self.match_index[peer] >= N:
                    count += 2
            if count > len(self.peers) // 2 and self.log[N].term == self.current_term:
                old_commit = self.commit_index
                self.commit_index = N
                logger.debug(f"[{self.node_id}] Commit index advanced {old_commit} -> {self.commit_index}")
                self._apply_entries(old_commit)
                break

    def xǁRaftNodeǁ_advance_commit_index__mutmut_18(self):
        if self.state != RaftState.LEADER:
            return
        # Find highest N > commit_index such that a majority have match_index >= N and log[N].term == current_term
        for N in range(len(self.log) - 1, self.commit_index, -1):
            count = 1  # leader itself
            for peer in self.peers:
                if self.match_index[peer] >= N:
                    count += 1
            if count > len(self.peers) // 2 or self.log[N].term == self.current_term:
                old_commit = self.commit_index
                self.commit_index = N
                logger.debug(f"[{self.node_id}] Commit index advanced {old_commit} -> {self.commit_index}")
                self._apply_entries(old_commit)
                break

    def xǁRaftNodeǁ_advance_commit_index__mutmut_19(self):
        if self.state != RaftState.LEADER:
            return
        # Find highest N > commit_index such that a majority have match_index >= N and log[N].term == current_term
        for N in range(len(self.log) - 1, self.commit_index, -1):
            count = 1  # leader itself
            for peer in self.peers:
                if self.match_index[peer] >= N:
                    count += 1
            if count >= len(self.peers) // 2 and self.log[N].term == self.current_term:
                old_commit = self.commit_index
                self.commit_index = N
                logger.debug(f"[{self.node_id}] Commit index advanced {old_commit} -> {self.commit_index}")
                self._apply_entries(old_commit)
                break

    def xǁRaftNodeǁ_advance_commit_index__mutmut_20(self):
        if self.state != RaftState.LEADER:
            return
        # Find highest N > commit_index such that a majority have match_index >= N and log[N].term == current_term
        for N in range(len(self.log) - 1, self.commit_index, -1):
            count = 1  # leader itself
            for peer in self.peers:
                if self.match_index[peer] >= N:
                    count += 1
            if count > len(self.peers) / 2 and self.log[N].term == self.current_term:
                old_commit = self.commit_index
                self.commit_index = N
                logger.debug(f"[{self.node_id}] Commit index advanced {old_commit} -> {self.commit_index}")
                self._apply_entries(old_commit)
                break

    def xǁRaftNodeǁ_advance_commit_index__mutmut_21(self):
        if self.state != RaftState.LEADER:
            return
        # Find highest N > commit_index such that a majority have match_index >= N and log[N].term == current_term
        for N in range(len(self.log) - 1, self.commit_index, -1):
            count = 1  # leader itself
            for peer in self.peers:
                if self.match_index[peer] >= N:
                    count += 1
            if count > len(self.peers) // 3 and self.log[N].term == self.current_term:
                old_commit = self.commit_index
                self.commit_index = N
                logger.debug(f"[{self.node_id}] Commit index advanced {old_commit} -> {self.commit_index}")
                self._apply_entries(old_commit)
                break

    def xǁRaftNodeǁ_advance_commit_index__mutmut_22(self):
        if self.state != RaftState.LEADER:
            return
        # Find highest N > commit_index such that a majority have match_index >= N and log[N].term == current_term
        for N in range(len(self.log) - 1, self.commit_index, -1):
            count = 1  # leader itself
            for peer in self.peers:
                if self.match_index[peer] >= N:
                    count += 1
            if count > len(self.peers) // 2 and self.log[N].term != self.current_term:
                old_commit = self.commit_index
                self.commit_index = N
                logger.debug(f"[{self.node_id}] Commit index advanced {old_commit} -> {self.commit_index}")
                self._apply_entries(old_commit)
                break

    def xǁRaftNodeǁ_advance_commit_index__mutmut_23(self):
        if self.state != RaftState.LEADER:
            return
        # Find highest N > commit_index such that a majority have match_index >= N and log[N].term == current_term
        for N in range(len(self.log) - 1, self.commit_index, -1):
            count = 1  # leader itself
            for peer in self.peers:
                if self.match_index[peer] >= N:
                    count += 1
            if count > len(self.peers) // 2 and self.log[N].term == self.current_term:
                old_commit = None
                self.commit_index = N
                logger.debug(f"[{self.node_id}] Commit index advanced {old_commit} -> {self.commit_index}")
                self._apply_entries(old_commit)
                break

    def xǁRaftNodeǁ_advance_commit_index__mutmut_24(self):
        if self.state != RaftState.LEADER:
            return
        # Find highest N > commit_index such that a majority have match_index >= N and log[N].term == current_term
        for N in range(len(self.log) - 1, self.commit_index, -1):
            count = 1  # leader itself
            for peer in self.peers:
                if self.match_index[peer] >= N:
                    count += 1
            if count > len(self.peers) // 2 and self.log[N].term == self.current_term:
                old_commit = self.commit_index
                self.commit_index = None
                logger.debug(f"[{self.node_id}] Commit index advanced {old_commit} -> {self.commit_index}")
                self._apply_entries(old_commit)
                break

    def xǁRaftNodeǁ_advance_commit_index__mutmut_25(self):
        if self.state != RaftState.LEADER:
            return
        # Find highest N > commit_index such that a majority have match_index >= N and log[N].term == current_term
        for N in range(len(self.log) - 1, self.commit_index, -1):
            count = 1  # leader itself
            for peer in self.peers:
                if self.match_index[peer] >= N:
                    count += 1
            if count > len(self.peers) // 2 and self.log[N].term == self.current_term:
                old_commit = self.commit_index
                self.commit_index = N
                logger.debug(None)
                self._apply_entries(old_commit)
                break

    def xǁRaftNodeǁ_advance_commit_index__mutmut_26(self):
        if self.state != RaftState.LEADER:
            return
        # Find highest N > commit_index such that a majority have match_index >= N and log[N].term == current_term
        for N in range(len(self.log) - 1, self.commit_index, -1):
            count = 1  # leader itself
            for peer in self.peers:
                if self.match_index[peer] >= N:
                    count += 1
            if count > len(self.peers) // 2 and self.log[N].term == self.current_term:
                old_commit = self.commit_index
                self.commit_index = N
                logger.debug(f"[{self.node_id}] Commit index advanced {old_commit} -> {self.commit_index}")
                self._apply_entries(None)
                break

    def xǁRaftNodeǁ_advance_commit_index__mutmut_27(self):
        if self.state != RaftState.LEADER:
            return
        # Find highest N > commit_index such that a majority have match_index >= N and log[N].term == current_term
        for N in range(len(self.log) - 1, self.commit_index, -1):
            count = 1  # leader itself
            for peer in self.peers:
                if self.match_index[peer] >= N:
                    count += 1
            if count > len(self.peers) // 2 and self.log[N].term == self.current_term:
                old_commit = self.commit_index
                self.commit_index = N
                logger.debug(f"[{self.node_id}] Commit index advanced {old_commit} -> {self.commit_index}")
                self._apply_entries(old_commit)
                return
    
    xǁRaftNodeǁ_advance_commit_index__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁRaftNodeǁ_advance_commit_index__mutmut_1': xǁRaftNodeǁ_advance_commit_index__mutmut_1, 
        'xǁRaftNodeǁ_advance_commit_index__mutmut_2': xǁRaftNodeǁ_advance_commit_index__mutmut_2, 
        'xǁRaftNodeǁ_advance_commit_index__mutmut_3': xǁRaftNodeǁ_advance_commit_index__mutmut_3, 
        'xǁRaftNodeǁ_advance_commit_index__mutmut_4': xǁRaftNodeǁ_advance_commit_index__mutmut_4, 
        'xǁRaftNodeǁ_advance_commit_index__mutmut_5': xǁRaftNodeǁ_advance_commit_index__mutmut_5, 
        'xǁRaftNodeǁ_advance_commit_index__mutmut_6': xǁRaftNodeǁ_advance_commit_index__mutmut_6, 
        'xǁRaftNodeǁ_advance_commit_index__mutmut_7': xǁRaftNodeǁ_advance_commit_index__mutmut_7, 
        'xǁRaftNodeǁ_advance_commit_index__mutmut_8': xǁRaftNodeǁ_advance_commit_index__mutmut_8, 
        'xǁRaftNodeǁ_advance_commit_index__mutmut_9': xǁRaftNodeǁ_advance_commit_index__mutmut_9, 
        'xǁRaftNodeǁ_advance_commit_index__mutmut_10': xǁRaftNodeǁ_advance_commit_index__mutmut_10, 
        'xǁRaftNodeǁ_advance_commit_index__mutmut_11': xǁRaftNodeǁ_advance_commit_index__mutmut_11, 
        'xǁRaftNodeǁ_advance_commit_index__mutmut_12': xǁRaftNodeǁ_advance_commit_index__mutmut_12, 
        'xǁRaftNodeǁ_advance_commit_index__mutmut_13': xǁRaftNodeǁ_advance_commit_index__mutmut_13, 
        'xǁRaftNodeǁ_advance_commit_index__mutmut_14': xǁRaftNodeǁ_advance_commit_index__mutmut_14, 
        'xǁRaftNodeǁ_advance_commit_index__mutmut_15': xǁRaftNodeǁ_advance_commit_index__mutmut_15, 
        'xǁRaftNodeǁ_advance_commit_index__mutmut_16': xǁRaftNodeǁ_advance_commit_index__mutmut_16, 
        'xǁRaftNodeǁ_advance_commit_index__mutmut_17': xǁRaftNodeǁ_advance_commit_index__mutmut_17, 
        'xǁRaftNodeǁ_advance_commit_index__mutmut_18': xǁRaftNodeǁ_advance_commit_index__mutmut_18, 
        'xǁRaftNodeǁ_advance_commit_index__mutmut_19': xǁRaftNodeǁ_advance_commit_index__mutmut_19, 
        'xǁRaftNodeǁ_advance_commit_index__mutmut_20': xǁRaftNodeǁ_advance_commit_index__mutmut_20, 
        'xǁRaftNodeǁ_advance_commit_index__mutmut_21': xǁRaftNodeǁ_advance_commit_index__mutmut_21, 
        'xǁRaftNodeǁ_advance_commit_index__mutmut_22': xǁRaftNodeǁ_advance_commit_index__mutmut_22, 
        'xǁRaftNodeǁ_advance_commit_index__mutmut_23': xǁRaftNodeǁ_advance_commit_index__mutmut_23, 
        'xǁRaftNodeǁ_advance_commit_index__mutmut_24': xǁRaftNodeǁ_advance_commit_index__mutmut_24, 
        'xǁRaftNodeǁ_advance_commit_index__mutmut_25': xǁRaftNodeǁ_advance_commit_index__mutmut_25, 
        'xǁRaftNodeǁ_advance_commit_index__mutmut_26': xǁRaftNodeǁ_advance_commit_index__mutmut_26, 
        'xǁRaftNodeǁ_advance_commit_index__mutmut_27': xǁRaftNodeǁ_advance_commit_index__mutmut_27
    }
    
    def _advance_commit_index(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁRaftNodeǁ_advance_commit_index__mutmut_orig"), object.__getattribute__(self, "xǁRaftNodeǁ_advance_commit_index__mutmut_mutants"), args, kwargs, self)
        return result 
    
    _advance_commit_index.__signature__ = _mutmut_signature(xǁRaftNodeǁ_advance_commit_index__mutmut_orig)
    xǁRaftNodeǁ_advance_commit_index__mutmut_orig.__name__ = 'xǁRaftNodeǁ_advance_commit_index'

    # ------------------------------------------------------------------
    # Apply State Machine
    # ------------------------------------------------------------------
    def xǁRaftNodeǁ_apply_entries__mutmut_orig(self, from_index: int):
        for i in range(from_index + 1, self.commit_index + 1):
            if i < len(self.log):
                entry = self.log[i]
                self.last_applied = i
                for cb in self.apply_callbacks:
                    try:
                        cb(entry)
                    except Exception as e:  # pragma: no cover - defensive
                        logger.error(f"Apply callback error: {e}")

    # ------------------------------------------------------------------
    # Apply State Machine
    # ------------------------------------------------------------------
    def xǁRaftNodeǁ_apply_entries__mutmut_1(self, from_index: int):
        for i in range(None, self.commit_index + 1):
            if i < len(self.log):
                entry = self.log[i]
                self.last_applied = i
                for cb in self.apply_callbacks:
                    try:
                        cb(entry)
                    except Exception as e:  # pragma: no cover - defensive
                        logger.error(f"Apply callback error: {e}")

    # ------------------------------------------------------------------
    # Apply State Machine
    # ------------------------------------------------------------------
    def xǁRaftNodeǁ_apply_entries__mutmut_2(self, from_index: int):
        for i in range(from_index + 1, None):
            if i < len(self.log):
                entry = self.log[i]
                self.last_applied = i
                for cb in self.apply_callbacks:
                    try:
                        cb(entry)
                    except Exception as e:  # pragma: no cover - defensive
                        logger.error(f"Apply callback error: {e}")

    # ------------------------------------------------------------------
    # Apply State Machine
    # ------------------------------------------------------------------
    def xǁRaftNodeǁ_apply_entries__mutmut_3(self, from_index: int):
        for i in range(self.commit_index + 1):
            if i < len(self.log):
                entry = self.log[i]
                self.last_applied = i
                for cb in self.apply_callbacks:
                    try:
                        cb(entry)
                    except Exception as e:  # pragma: no cover - defensive
                        logger.error(f"Apply callback error: {e}")

    # ------------------------------------------------------------------
    # Apply State Machine
    # ------------------------------------------------------------------
    def xǁRaftNodeǁ_apply_entries__mutmut_4(self, from_index: int):
        for i in range(from_index + 1, ):
            if i < len(self.log):
                entry = self.log[i]
                self.last_applied = i
                for cb in self.apply_callbacks:
                    try:
                        cb(entry)
                    except Exception as e:  # pragma: no cover - defensive
                        logger.error(f"Apply callback error: {e}")

    # ------------------------------------------------------------------
    # Apply State Machine
    # ------------------------------------------------------------------
    def xǁRaftNodeǁ_apply_entries__mutmut_5(self, from_index: int):
        for i in range(from_index - 1, self.commit_index + 1):
            if i < len(self.log):
                entry = self.log[i]
                self.last_applied = i
                for cb in self.apply_callbacks:
                    try:
                        cb(entry)
                    except Exception as e:  # pragma: no cover - defensive
                        logger.error(f"Apply callback error: {e}")

    # ------------------------------------------------------------------
    # Apply State Machine
    # ------------------------------------------------------------------
    def xǁRaftNodeǁ_apply_entries__mutmut_6(self, from_index: int):
        for i in range(from_index + 2, self.commit_index + 1):
            if i < len(self.log):
                entry = self.log[i]
                self.last_applied = i
                for cb in self.apply_callbacks:
                    try:
                        cb(entry)
                    except Exception as e:  # pragma: no cover - defensive
                        logger.error(f"Apply callback error: {e}")

    # ------------------------------------------------------------------
    # Apply State Machine
    # ------------------------------------------------------------------
    def xǁRaftNodeǁ_apply_entries__mutmut_7(self, from_index: int):
        for i in range(from_index + 1, self.commit_index - 1):
            if i < len(self.log):
                entry = self.log[i]
                self.last_applied = i
                for cb in self.apply_callbacks:
                    try:
                        cb(entry)
                    except Exception as e:  # pragma: no cover - defensive
                        logger.error(f"Apply callback error: {e}")

    # ------------------------------------------------------------------
    # Apply State Machine
    # ------------------------------------------------------------------
    def xǁRaftNodeǁ_apply_entries__mutmut_8(self, from_index: int):
        for i in range(from_index + 1, self.commit_index + 2):
            if i < len(self.log):
                entry = self.log[i]
                self.last_applied = i
                for cb in self.apply_callbacks:
                    try:
                        cb(entry)
                    except Exception as e:  # pragma: no cover - defensive
                        logger.error(f"Apply callback error: {e}")

    # ------------------------------------------------------------------
    # Apply State Machine
    # ------------------------------------------------------------------
    def xǁRaftNodeǁ_apply_entries__mutmut_9(self, from_index: int):
        for i in range(from_index + 1, self.commit_index + 1):
            if i <= len(self.log):
                entry = self.log[i]
                self.last_applied = i
                for cb in self.apply_callbacks:
                    try:
                        cb(entry)
                    except Exception as e:  # pragma: no cover - defensive
                        logger.error(f"Apply callback error: {e}")

    # ------------------------------------------------------------------
    # Apply State Machine
    # ------------------------------------------------------------------
    def xǁRaftNodeǁ_apply_entries__mutmut_10(self, from_index: int):
        for i in range(from_index + 1, self.commit_index + 1):
            if i < len(self.log):
                entry = None
                self.last_applied = i
                for cb in self.apply_callbacks:
                    try:
                        cb(entry)
                    except Exception as e:  # pragma: no cover - defensive
                        logger.error(f"Apply callback error: {e}")

    # ------------------------------------------------------------------
    # Apply State Machine
    # ------------------------------------------------------------------
    def xǁRaftNodeǁ_apply_entries__mutmut_11(self, from_index: int):
        for i in range(from_index + 1, self.commit_index + 1):
            if i < len(self.log):
                entry = self.log[i]
                self.last_applied = None
                for cb in self.apply_callbacks:
                    try:
                        cb(entry)
                    except Exception as e:  # pragma: no cover - defensive
                        logger.error(f"Apply callback error: {e}")

    # ------------------------------------------------------------------
    # Apply State Machine
    # ------------------------------------------------------------------
    def xǁRaftNodeǁ_apply_entries__mutmut_12(self, from_index: int):
        for i in range(from_index + 1, self.commit_index + 1):
            if i < len(self.log):
                entry = self.log[i]
                self.last_applied = i
                for cb in self.apply_callbacks:
                    try:
                        cb(None)
                    except Exception as e:  # pragma: no cover - defensive
                        logger.error(f"Apply callback error: {e}")

    # ------------------------------------------------------------------
    # Apply State Machine
    # ------------------------------------------------------------------
    def xǁRaftNodeǁ_apply_entries__mutmut_13(self, from_index: int):
        for i in range(from_index + 1, self.commit_index + 1):
            if i < len(self.log):
                entry = self.log[i]
                self.last_applied = i
                for cb in self.apply_callbacks:
                    try:
                        cb(entry)
                    except Exception as e:  # pragma: no cover - defensive
                        logger.error(None)
    
    xǁRaftNodeǁ_apply_entries__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁRaftNodeǁ_apply_entries__mutmut_1': xǁRaftNodeǁ_apply_entries__mutmut_1, 
        'xǁRaftNodeǁ_apply_entries__mutmut_2': xǁRaftNodeǁ_apply_entries__mutmut_2, 
        'xǁRaftNodeǁ_apply_entries__mutmut_3': xǁRaftNodeǁ_apply_entries__mutmut_3, 
        'xǁRaftNodeǁ_apply_entries__mutmut_4': xǁRaftNodeǁ_apply_entries__mutmut_4, 
        'xǁRaftNodeǁ_apply_entries__mutmut_5': xǁRaftNodeǁ_apply_entries__mutmut_5, 
        'xǁRaftNodeǁ_apply_entries__mutmut_6': xǁRaftNodeǁ_apply_entries__mutmut_6, 
        'xǁRaftNodeǁ_apply_entries__mutmut_7': xǁRaftNodeǁ_apply_entries__mutmut_7, 
        'xǁRaftNodeǁ_apply_entries__mutmut_8': xǁRaftNodeǁ_apply_entries__mutmut_8, 
        'xǁRaftNodeǁ_apply_entries__mutmut_9': xǁRaftNodeǁ_apply_entries__mutmut_9, 
        'xǁRaftNodeǁ_apply_entries__mutmut_10': xǁRaftNodeǁ_apply_entries__mutmut_10, 
        'xǁRaftNodeǁ_apply_entries__mutmut_11': xǁRaftNodeǁ_apply_entries__mutmut_11, 
        'xǁRaftNodeǁ_apply_entries__mutmut_12': xǁRaftNodeǁ_apply_entries__mutmut_12, 
        'xǁRaftNodeǁ_apply_entries__mutmut_13': xǁRaftNodeǁ_apply_entries__mutmut_13
    }
    
    def _apply_entries(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁRaftNodeǁ_apply_entries__mutmut_orig"), object.__getattribute__(self, "xǁRaftNodeǁ_apply_entries__mutmut_mutants"), args, kwargs, self)
        return result 
    
    _apply_entries.__signature__ = _mutmut_signature(xǁRaftNodeǁ_apply_entries__mutmut_orig)
    xǁRaftNodeǁ_apply_entries__mutmut_orig.__name__ = 'xǁRaftNodeǁ_apply_entries'

    def xǁRaftNodeǁregister_apply_callback__mutmut_orig(self, callback: Callable[[LogEntry], None]):
        self.apply_callbacks.append(callback)

    def xǁRaftNodeǁregister_apply_callback__mutmut_1(self, callback: Callable[[LogEntry], None]):
        self.apply_callbacks.append(None)
    
    xǁRaftNodeǁregister_apply_callback__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁRaftNodeǁregister_apply_callback__mutmut_1': xǁRaftNodeǁregister_apply_callback__mutmut_1
    }
    
    def register_apply_callback(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁRaftNodeǁregister_apply_callback__mutmut_orig"), object.__getattribute__(self, "xǁRaftNodeǁregister_apply_callback__mutmut_mutants"), args, kwargs, self)
        return result 
    
    register_apply_callback.__signature__ = _mutmut_signature(xǁRaftNodeǁregister_apply_callback__mutmut_orig)
    xǁRaftNodeǁregister_apply_callback__mutmut_orig.__name__ = 'xǁRaftNodeǁregister_apply_callback'

    # ------------------------------------------------------------------
    # RPC Handlers (simulated inbound)
    # ------------------------------------------------------------------
    def xǁRaftNodeǁreceive_append_entries__mutmut_orig(self, term: int, leader_id: str, prev_log_index: int,
                               prev_log_term: int, entries: List[LogEntry], leader_commit: int) -> bool:
        if term < self.current_term:
            return False
        if term > self.current_term or self.state != RaftState.FOLLOWER:
            self._become_follower(term=term)
        self.last_activity = datetime.now()
        # Consistency check
        if prev_log_index >= len(self.log):
            return False
        if prev_log_index > 0 and self.log[prev_log_index].term != prev_log_term:
            return False
        # Append any new entries (overwrite conflicting)
        self.log = self.log[:prev_log_index + 1] + entries
        if leader_commit > self.commit_index:
            old_commit = self.commit_index
            self.commit_index = min(leader_commit, len(self.log) - 1)
            self._apply_entries(old_commit)
        return True

    # ------------------------------------------------------------------
    # RPC Handlers (simulated inbound)
    # ------------------------------------------------------------------
    def xǁRaftNodeǁreceive_append_entries__mutmut_1(self, term: int, leader_id: str, prev_log_index: int,
                               prev_log_term: int, entries: List[LogEntry], leader_commit: int) -> bool:
        if term <= self.current_term:
            return False
        if term > self.current_term or self.state != RaftState.FOLLOWER:
            self._become_follower(term=term)
        self.last_activity = datetime.now()
        # Consistency check
        if prev_log_index >= len(self.log):
            return False
        if prev_log_index > 0 and self.log[prev_log_index].term != prev_log_term:
            return False
        # Append any new entries (overwrite conflicting)
        self.log = self.log[:prev_log_index + 1] + entries
        if leader_commit > self.commit_index:
            old_commit = self.commit_index
            self.commit_index = min(leader_commit, len(self.log) - 1)
            self._apply_entries(old_commit)
        return True

    # ------------------------------------------------------------------
    # RPC Handlers (simulated inbound)
    # ------------------------------------------------------------------
    def xǁRaftNodeǁreceive_append_entries__mutmut_2(self, term: int, leader_id: str, prev_log_index: int,
                               prev_log_term: int, entries: List[LogEntry], leader_commit: int) -> bool:
        if term < self.current_term:
            return True
        if term > self.current_term or self.state != RaftState.FOLLOWER:
            self._become_follower(term=term)
        self.last_activity = datetime.now()
        # Consistency check
        if prev_log_index >= len(self.log):
            return False
        if prev_log_index > 0 and self.log[prev_log_index].term != prev_log_term:
            return False
        # Append any new entries (overwrite conflicting)
        self.log = self.log[:prev_log_index + 1] + entries
        if leader_commit > self.commit_index:
            old_commit = self.commit_index
            self.commit_index = min(leader_commit, len(self.log) - 1)
            self._apply_entries(old_commit)
        return True

    # ------------------------------------------------------------------
    # RPC Handlers (simulated inbound)
    # ------------------------------------------------------------------
    def xǁRaftNodeǁreceive_append_entries__mutmut_3(self, term: int, leader_id: str, prev_log_index: int,
                               prev_log_term: int, entries: List[LogEntry], leader_commit: int) -> bool:
        if term < self.current_term:
            return False
        if term > self.current_term and self.state != RaftState.FOLLOWER:
            self._become_follower(term=term)
        self.last_activity = datetime.now()
        # Consistency check
        if prev_log_index >= len(self.log):
            return False
        if prev_log_index > 0 and self.log[prev_log_index].term != prev_log_term:
            return False
        # Append any new entries (overwrite conflicting)
        self.log = self.log[:prev_log_index + 1] + entries
        if leader_commit > self.commit_index:
            old_commit = self.commit_index
            self.commit_index = min(leader_commit, len(self.log) - 1)
            self._apply_entries(old_commit)
        return True

    # ------------------------------------------------------------------
    # RPC Handlers (simulated inbound)
    # ------------------------------------------------------------------
    def xǁRaftNodeǁreceive_append_entries__mutmut_4(self, term: int, leader_id: str, prev_log_index: int,
                               prev_log_term: int, entries: List[LogEntry], leader_commit: int) -> bool:
        if term < self.current_term:
            return False
        if term >= self.current_term or self.state != RaftState.FOLLOWER:
            self._become_follower(term=term)
        self.last_activity = datetime.now()
        # Consistency check
        if prev_log_index >= len(self.log):
            return False
        if prev_log_index > 0 and self.log[prev_log_index].term != prev_log_term:
            return False
        # Append any new entries (overwrite conflicting)
        self.log = self.log[:prev_log_index + 1] + entries
        if leader_commit > self.commit_index:
            old_commit = self.commit_index
            self.commit_index = min(leader_commit, len(self.log) - 1)
            self._apply_entries(old_commit)
        return True

    # ------------------------------------------------------------------
    # RPC Handlers (simulated inbound)
    # ------------------------------------------------------------------
    def xǁRaftNodeǁreceive_append_entries__mutmut_5(self, term: int, leader_id: str, prev_log_index: int,
                               prev_log_term: int, entries: List[LogEntry], leader_commit: int) -> bool:
        if term < self.current_term:
            return False
        if term > self.current_term or self.state == RaftState.FOLLOWER:
            self._become_follower(term=term)
        self.last_activity = datetime.now()
        # Consistency check
        if prev_log_index >= len(self.log):
            return False
        if prev_log_index > 0 and self.log[prev_log_index].term != prev_log_term:
            return False
        # Append any new entries (overwrite conflicting)
        self.log = self.log[:prev_log_index + 1] + entries
        if leader_commit > self.commit_index:
            old_commit = self.commit_index
            self.commit_index = min(leader_commit, len(self.log) - 1)
            self._apply_entries(old_commit)
        return True

    # ------------------------------------------------------------------
    # RPC Handlers (simulated inbound)
    # ------------------------------------------------------------------
    def xǁRaftNodeǁreceive_append_entries__mutmut_6(self, term: int, leader_id: str, prev_log_index: int,
                               prev_log_term: int, entries: List[LogEntry], leader_commit: int) -> bool:
        if term < self.current_term:
            return False
        if term > self.current_term or self.state != RaftState.FOLLOWER:
            self._become_follower(term=None)
        self.last_activity = datetime.now()
        # Consistency check
        if prev_log_index >= len(self.log):
            return False
        if prev_log_index > 0 and self.log[prev_log_index].term != prev_log_term:
            return False
        # Append any new entries (overwrite conflicting)
        self.log = self.log[:prev_log_index + 1] + entries
        if leader_commit > self.commit_index:
            old_commit = self.commit_index
            self.commit_index = min(leader_commit, len(self.log) - 1)
            self._apply_entries(old_commit)
        return True

    # ------------------------------------------------------------------
    # RPC Handlers (simulated inbound)
    # ------------------------------------------------------------------
    def xǁRaftNodeǁreceive_append_entries__mutmut_7(self, term: int, leader_id: str, prev_log_index: int,
                               prev_log_term: int, entries: List[LogEntry], leader_commit: int) -> bool:
        if term < self.current_term:
            return False
        if term > self.current_term or self.state != RaftState.FOLLOWER:
            self._become_follower(term=term)
        self.last_activity = None
        # Consistency check
        if prev_log_index >= len(self.log):
            return False
        if prev_log_index > 0 and self.log[prev_log_index].term != prev_log_term:
            return False
        # Append any new entries (overwrite conflicting)
        self.log = self.log[:prev_log_index + 1] + entries
        if leader_commit > self.commit_index:
            old_commit = self.commit_index
            self.commit_index = min(leader_commit, len(self.log) - 1)
            self._apply_entries(old_commit)
        return True

    # ------------------------------------------------------------------
    # RPC Handlers (simulated inbound)
    # ------------------------------------------------------------------
    def xǁRaftNodeǁreceive_append_entries__mutmut_8(self, term: int, leader_id: str, prev_log_index: int,
                               prev_log_term: int, entries: List[LogEntry], leader_commit: int) -> bool:
        if term < self.current_term:
            return False
        if term > self.current_term or self.state != RaftState.FOLLOWER:
            self._become_follower(term=term)
        self.last_activity = datetime.now()
        # Consistency check
        if prev_log_index > len(self.log):
            return False
        if prev_log_index > 0 and self.log[prev_log_index].term != prev_log_term:
            return False
        # Append any new entries (overwrite conflicting)
        self.log = self.log[:prev_log_index + 1] + entries
        if leader_commit > self.commit_index:
            old_commit = self.commit_index
            self.commit_index = min(leader_commit, len(self.log) - 1)
            self._apply_entries(old_commit)
        return True

    # ------------------------------------------------------------------
    # RPC Handlers (simulated inbound)
    # ------------------------------------------------------------------
    def xǁRaftNodeǁreceive_append_entries__mutmut_9(self, term: int, leader_id: str, prev_log_index: int,
                               prev_log_term: int, entries: List[LogEntry], leader_commit: int) -> bool:
        if term < self.current_term:
            return False
        if term > self.current_term or self.state != RaftState.FOLLOWER:
            self._become_follower(term=term)
        self.last_activity = datetime.now()
        # Consistency check
        if prev_log_index >= len(self.log):
            return True
        if prev_log_index > 0 and self.log[prev_log_index].term != prev_log_term:
            return False
        # Append any new entries (overwrite conflicting)
        self.log = self.log[:prev_log_index + 1] + entries
        if leader_commit > self.commit_index:
            old_commit = self.commit_index
            self.commit_index = min(leader_commit, len(self.log) - 1)
            self._apply_entries(old_commit)
        return True

    # ------------------------------------------------------------------
    # RPC Handlers (simulated inbound)
    # ------------------------------------------------------------------
    def xǁRaftNodeǁreceive_append_entries__mutmut_10(self, term: int, leader_id: str, prev_log_index: int,
                               prev_log_term: int, entries: List[LogEntry], leader_commit: int) -> bool:
        if term < self.current_term:
            return False
        if term > self.current_term or self.state != RaftState.FOLLOWER:
            self._become_follower(term=term)
        self.last_activity = datetime.now()
        # Consistency check
        if prev_log_index >= len(self.log):
            return False
        if prev_log_index > 0 or self.log[prev_log_index].term != prev_log_term:
            return False
        # Append any new entries (overwrite conflicting)
        self.log = self.log[:prev_log_index + 1] + entries
        if leader_commit > self.commit_index:
            old_commit = self.commit_index
            self.commit_index = min(leader_commit, len(self.log) - 1)
            self._apply_entries(old_commit)
        return True

    # ------------------------------------------------------------------
    # RPC Handlers (simulated inbound)
    # ------------------------------------------------------------------
    def xǁRaftNodeǁreceive_append_entries__mutmut_11(self, term: int, leader_id: str, prev_log_index: int,
                               prev_log_term: int, entries: List[LogEntry], leader_commit: int) -> bool:
        if term < self.current_term:
            return False
        if term > self.current_term or self.state != RaftState.FOLLOWER:
            self._become_follower(term=term)
        self.last_activity = datetime.now()
        # Consistency check
        if prev_log_index >= len(self.log):
            return False
        if prev_log_index >= 0 and self.log[prev_log_index].term != prev_log_term:
            return False
        # Append any new entries (overwrite conflicting)
        self.log = self.log[:prev_log_index + 1] + entries
        if leader_commit > self.commit_index:
            old_commit = self.commit_index
            self.commit_index = min(leader_commit, len(self.log) - 1)
            self._apply_entries(old_commit)
        return True

    # ------------------------------------------------------------------
    # RPC Handlers (simulated inbound)
    # ------------------------------------------------------------------
    def xǁRaftNodeǁreceive_append_entries__mutmut_12(self, term: int, leader_id: str, prev_log_index: int,
                               prev_log_term: int, entries: List[LogEntry], leader_commit: int) -> bool:
        if term < self.current_term:
            return False
        if term > self.current_term or self.state != RaftState.FOLLOWER:
            self._become_follower(term=term)
        self.last_activity = datetime.now()
        # Consistency check
        if prev_log_index >= len(self.log):
            return False
        if prev_log_index > 1 and self.log[prev_log_index].term != prev_log_term:
            return False
        # Append any new entries (overwrite conflicting)
        self.log = self.log[:prev_log_index + 1] + entries
        if leader_commit > self.commit_index:
            old_commit = self.commit_index
            self.commit_index = min(leader_commit, len(self.log) - 1)
            self._apply_entries(old_commit)
        return True

    # ------------------------------------------------------------------
    # RPC Handlers (simulated inbound)
    # ------------------------------------------------------------------
    def xǁRaftNodeǁreceive_append_entries__mutmut_13(self, term: int, leader_id: str, prev_log_index: int,
                               prev_log_term: int, entries: List[LogEntry], leader_commit: int) -> bool:
        if term < self.current_term:
            return False
        if term > self.current_term or self.state != RaftState.FOLLOWER:
            self._become_follower(term=term)
        self.last_activity = datetime.now()
        # Consistency check
        if prev_log_index >= len(self.log):
            return False
        if prev_log_index > 0 and self.log[prev_log_index].term == prev_log_term:
            return False
        # Append any new entries (overwrite conflicting)
        self.log = self.log[:prev_log_index + 1] + entries
        if leader_commit > self.commit_index:
            old_commit = self.commit_index
            self.commit_index = min(leader_commit, len(self.log) - 1)
            self._apply_entries(old_commit)
        return True

    # ------------------------------------------------------------------
    # RPC Handlers (simulated inbound)
    # ------------------------------------------------------------------
    def xǁRaftNodeǁreceive_append_entries__mutmut_14(self, term: int, leader_id: str, prev_log_index: int,
                               prev_log_term: int, entries: List[LogEntry], leader_commit: int) -> bool:
        if term < self.current_term:
            return False
        if term > self.current_term or self.state != RaftState.FOLLOWER:
            self._become_follower(term=term)
        self.last_activity = datetime.now()
        # Consistency check
        if prev_log_index >= len(self.log):
            return False
        if prev_log_index > 0 and self.log[prev_log_index].term != prev_log_term:
            return True
        # Append any new entries (overwrite conflicting)
        self.log = self.log[:prev_log_index + 1] + entries
        if leader_commit > self.commit_index:
            old_commit = self.commit_index
            self.commit_index = min(leader_commit, len(self.log) - 1)
            self._apply_entries(old_commit)
        return True

    # ------------------------------------------------------------------
    # RPC Handlers (simulated inbound)
    # ------------------------------------------------------------------
    def xǁRaftNodeǁreceive_append_entries__mutmut_15(self, term: int, leader_id: str, prev_log_index: int,
                               prev_log_term: int, entries: List[LogEntry], leader_commit: int) -> bool:
        if term < self.current_term:
            return False
        if term > self.current_term or self.state != RaftState.FOLLOWER:
            self._become_follower(term=term)
        self.last_activity = datetime.now()
        # Consistency check
        if prev_log_index >= len(self.log):
            return False
        if prev_log_index > 0 and self.log[prev_log_index].term != prev_log_term:
            return False
        # Append any new entries (overwrite conflicting)
        self.log = None
        if leader_commit > self.commit_index:
            old_commit = self.commit_index
            self.commit_index = min(leader_commit, len(self.log) - 1)
            self._apply_entries(old_commit)
        return True

    # ------------------------------------------------------------------
    # RPC Handlers (simulated inbound)
    # ------------------------------------------------------------------
    def xǁRaftNodeǁreceive_append_entries__mutmut_16(self, term: int, leader_id: str, prev_log_index: int,
                               prev_log_term: int, entries: List[LogEntry], leader_commit: int) -> bool:
        if term < self.current_term:
            return False
        if term > self.current_term or self.state != RaftState.FOLLOWER:
            self._become_follower(term=term)
        self.last_activity = datetime.now()
        # Consistency check
        if prev_log_index >= len(self.log):
            return False
        if prev_log_index > 0 and self.log[prev_log_index].term != prev_log_term:
            return False
        # Append any new entries (overwrite conflicting)
        self.log = self.log[:prev_log_index + 1] - entries
        if leader_commit > self.commit_index:
            old_commit = self.commit_index
            self.commit_index = min(leader_commit, len(self.log) - 1)
            self._apply_entries(old_commit)
        return True

    # ------------------------------------------------------------------
    # RPC Handlers (simulated inbound)
    # ------------------------------------------------------------------
    def xǁRaftNodeǁreceive_append_entries__mutmut_17(self, term: int, leader_id: str, prev_log_index: int,
                               prev_log_term: int, entries: List[LogEntry], leader_commit: int) -> bool:
        if term < self.current_term:
            return False
        if term > self.current_term or self.state != RaftState.FOLLOWER:
            self._become_follower(term=term)
        self.last_activity = datetime.now()
        # Consistency check
        if prev_log_index >= len(self.log):
            return False
        if prev_log_index > 0 and self.log[prev_log_index].term != prev_log_term:
            return False
        # Append any new entries (overwrite conflicting)
        self.log = self.log[:prev_log_index - 1] + entries
        if leader_commit > self.commit_index:
            old_commit = self.commit_index
            self.commit_index = min(leader_commit, len(self.log) - 1)
            self._apply_entries(old_commit)
        return True

    # ------------------------------------------------------------------
    # RPC Handlers (simulated inbound)
    # ------------------------------------------------------------------
    def xǁRaftNodeǁreceive_append_entries__mutmut_18(self, term: int, leader_id: str, prev_log_index: int,
                               prev_log_term: int, entries: List[LogEntry], leader_commit: int) -> bool:
        if term < self.current_term:
            return False
        if term > self.current_term or self.state != RaftState.FOLLOWER:
            self._become_follower(term=term)
        self.last_activity = datetime.now()
        # Consistency check
        if prev_log_index >= len(self.log):
            return False
        if prev_log_index > 0 and self.log[prev_log_index].term != prev_log_term:
            return False
        # Append any new entries (overwrite conflicting)
        self.log = self.log[:prev_log_index + 2] + entries
        if leader_commit > self.commit_index:
            old_commit = self.commit_index
            self.commit_index = min(leader_commit, len(self.log) - 1)
            self._apply_entries(old_commit)
        return True

    # ------------------------------------------------------------------
    # RPC Handlers (simulated inbound)
    # ------------------------------------------------------------------
    def xǁRaftNodeǁreceive_append_entries__mutmut_19(self, term: int, leader_id: str, prev_log_index: int,
                               prev_log_term: int, entries: List[LogEntry], leader_commit: int) -> bool:
        if term < self.current_term:
            return False
        if term > self.current_term or self.state != RaftState.FOLLOWER:
            self._become_follower(term=term)
        self.last_activity = datetime.now()
        # Consistency check
        if prev_log_index >= len(self.log):
            return False
        if prev_log_index > 0 and self.log[prev_log_index].term != prev_log_term:
            return False
        # Append any new entries (overwrite conflicting)
        self.log = self.log[:prev_log_index + 1] + entries
        if leader_commit >= self.commit_index:
            old_commit = self.commit_index
            self.commit_index = min(leader_commit, len(self.log) - 1)
            self._apply_entries(old_commit)
        return True

    # ------------------------------------------------------------------
    # RPC Handlers (simulated inbound)
    # ------------------------------------------------------------------
    def xǁRaftNodeǁreceive_append_entries__mutmut_20(self, term: int, leader_id: str, prev_log_index: int,
                               prev_log_term: int, entries: List[LogEntry], leader_commit: int) -> bool:
        if term < self.current_term:
            return False
        if term > self.current_term or self.state != RaftState.FOLLOWER:
            self._become_follower(term=term)
        self.last_activity = datetime.now()
        # Consistency check
        if prev_log_index >= len(self.log):
            return False
        if prev_log_index > 0 and self.log[prev_log_index].term != prev_log_term:
            return False
        # Append any new entries (overwrite conflicting)
        self.log = self.log[:prev_log_index + 1] + entries
        if leader_commit > self.commit_index:
            old_commit = None
            self.commit_index = min(leader_commit, len(self.log) - 1)
            self._apply_entries(old_commit)
        return True

    # ------------------------------------------------------------------
    # RPC Handlers (simulated inbound)
    # ------------------------------------------------------------------
    def xǁRaftNodeǁreceive_append_entries__mutmut_21(self, term: int, leader_id: str, prev_log_index: int,
                               prev_log_term: int, entries: List[LogEntry], leader_commit: int) -> bool:
        if term < self.current_term:
            return False
        if term > self.current_term or self.state != RaftState.FOLLOWER:
            self._become_follower(term=term)
        self.last_activity = datetime.now()
        # Consistency check
        if prev_log_index >= len(self.log):
            return False
        if prev_log_index > 0 and self.log[prev_log_index].term != prev_log_term:
            return False
        # Append any new entries (overwrite conflicting)
        self.log = self.log[:prev_log_index + 1] + entries
        if leader_commit > self.commit_index:
            old_commit = self.commit_index
            self.commit_index = None
            self._apply_entries(old_commit)
        return True

    # ------------------------------------------------------------------
    # RPC Handlers (simulated inbound)
    # ------------------------------------------------------------------
    def xǁRaftNodeǁreceive_append_entries__mutmut_22(self, term: int, leader_id: str, prev_log_index: int,
                               prev_log_term: int, entries: List[LogEntry], leader_commit: int) -> bool:
        if term < self.current_term:
            return False
        if term > self.current_term or self.state != RaftState.FOLLOWER:
            self._become_follower(term=term)
        self.last_activity = datetime.now()
        # Consistency check
        if prev_log_index >= len(self.log):
            return False
        if prev_log_index > 0 and self.log[prev_log_index].term != prev_log_term:
            return False
        # Append any new entries (overwrite conflicting)
        self.log = self.log[:prev_log_index + 1] + entries
        if leader_commit > self.commit_index:
            old_commit = self.commit_index
            self.commit_index = min(None, len(self.log) - 1)
            self._apply_entries(old_commit)
        return True

    # ------------------------------------------------------------------
    # RPC Handlers (simulated inbound)
    # ------------------------------------------------------------------
    def xǁRaftNodeǁreceive_append_entries__mutmut_23(self, term: int, leader_id: str, prev_log_index: int,
                               prev_log_term: int, entries: List[LogEntry], leader_commit: int) -> bool:
        if term < self.current_term:
            return False
        if term > self.current_term or self.state != RaftState.FOLLOWER:
            self._become_follower(term=term)
        self.last_activity = datetime.now()
        # Consistency check
        if prev_log_index >= len(self.log):
            return False
        if prev_log_index > 0 and self.log[prev_log_index].term != prev_log_term:
            return False
        # Append any new entries (overwrite conflicting)
        self.log = self.log[:prev_log_index + 1] + entries
        if leader_commit > self.commit_index:
            old_commit = self.commit_index
            self.commit_index = min(leader_commit, None)
            self._apply_entries(old_commit)
        return True

    # ------------------------------------------------------------------
    # RPC Handlers (simulated inbound)
    # ------------------------------------------------------------------
    def xǁRaftNodeǁreceive_append_entries__mutmut_24(self, term: int, leader_id: str, prev_log_index: int,
                               prev_log_term: int, entries: List[LogEntry], leader_commit: int) -> bool:
        if term < self.current_term:
            return False
        if term > self.current_term or self.state != RaftState.FOLLOWER:
            self._become_follower(term=term)
        self.last_activity = datetime.now()
        # Consistency check
        if prev_log_index >= len(self.log):
            return False
        if prev_log_index > 0 and self.log[prev_log_index].term != prev_log_term:
            return False
        # Append any new entries (overwrite conflicting)
        self.log = self.log[:prev_log_index + 1] + entries
        if leader_commit > self.commit_index:
            old_commit = self.commit_index
            self.commit_index = min(len(self.log) - 1)
            self._apply_entries(old_commit)
        return True

    # ------------------------------------------------------------------
    # RPC Handlers (simulated inbound)
    # ------------------------------------------------------------------
    def xǁRaftNodeǁreceive_append_entries__mutmut_25(self, term: int, leader_id: str, prev_log_index: int,
                               prev_log_term: int, entries: List[LogEntry], leader_commit: int) -> bool:
        if term < self.current_term:
            return False
        if term > self.current_term or self.state != RaftState.FOLLOWER:
            self._become_follower(term=term)
        self.last_activity = datetime.now()
        # Consistency check
        if prev_log_index >= len(self.log):
            return False
        if prev_log_index > 0 and self.log[prev_log_index].term != prev_log_term:
            return False
        # Append any new entries (overwrite conflicting)
        self.log = self.log[:prev_log_index + 1] + entries
        if leader_commit > self.commit_index:
            old_commit = self.commit_index
            self.commit_index = min(leader_commit, )
            self._apply_entries(old_commit)
        return True

    # ------------------------------------------------------------------
    # RPC Handlers (simulated inbound)
    # ------------------------------------------------------------------
    def xǁRaftNodeǁreceive_append_entries__mutmut_26(self, term: int, leader_id: str, prev_log_index: int,
                               prev_log_term: int, entries: List[LogEntry], leader_commit: int) -> bool:
        if term < self.current_term:
            return False
        if term > self.current_term or self.state != RaftState.FOLLOWER:
            self._become_follower(term=term)
        self.last_activity = datetime.now()
        # Consistency check
        if prev_log_index >= len(self.log):
            return False
        if prev_log_index > 0 and self.log[prev_log_index].term != prev_log_term:
            return False
        # Append any new entries (overwrite conflicting)
        self.log = self.log[:prev_log_index + 1] + entries
        if leader_commit > self.commit_index:
            old_commit = self.commit_index
            self.commit_index = min(leader_commit, len(self.log) + 1)
            self._apply_entries(old_commit)
        return True

    # ------------------------------------------------------------------
    # RPC Handlers (simulated inbound)
    # ------------------------------------------------------------------
    def xǁRaftNodeǁreceive_append_entries__mutmut_27(self, term: int, leader_id: str, prev_log_index: int,
                               prev_log_term: int, entries: List[LogEntry], leader_commit: int) -> bool:
        if term < self.current_term:
            return False
        if term > self.current_term or self.state != RaftState.FOLLOWER:
            self._become_follower(term=term)
        self.last_activity = datetime.now()
        # Consistency check
        if prev_log_index >= len(self.log):
            return False
        if prev_log_index > 0 and self.log[prev_log_index].term != prev_log_term:
            return False
        # Append any new entries (overwrite conflicting)
        self.log = self.log[:prev_log_index + 1] + entries
        if leader_commit > self.commit_index:
            old_commit = self.commit_index
            self.commit_index = min(leader_commit, len(self.log) - 2)
            self._apply_entries(old_commit)
        return True

    # ------------------------------------------------------------------
    # RPC Handlers (simulated inbound)
    # ------------------------------------------------------------------
    def xǁRaftNodeǁreceive_append_entries__mutmut_28(self, term: int, leader_id: str, prev_log_index: int,
                               prev_log_term: int, entries: List[LogEntry], leader_commit: int) -> bool:
        if term < self.current_term:
            return False
        if term > self.current_term or self.state != RaftState.FOLLOWER:
            self._become_follower(term=term)
        self.last_activity = datetime.now()
        # Consistency check
        if prev_log_index >= len(self.log):
            return False
        if prev_log_index > 0 and self.log[prev_log_index].term != prev_log_term:
            return False
        # Append any new entries (overwrite conflicting)
        self.log = self.log[:prev_log_index + 1] + entries
        if leader_commit > self.commit_index:
            old_commit = self.commit_index
            self.commit_index = min(leader_commit, len(self.log) - 1)
            self._apply_entries(None)
        return True

    # ------------------------------------------------------------------
    # RPC Handlers (simulated inbound)
    # ------------------------------------------------------------------
    def xǁRaftNodeǁreceive_append_entries__mutmut_29(self, term: int, leader_id: str, prev_log_index: int,
                               prev_log_term: int, entries: List[LogEntry], leader_commit: int) -> bool:
        if term < self.current_term:
            return False
        if term > self.current_term or self.state != RaftState.FOLLOWER:
            self._become_follower(term=term)
        self.last_activity = datetime.now()
        # Consistency check
        if prev_log_index >= len(self.log):
            return False
        if prev_log_index > 0 and self.log[prev_log_index].term != prev_log_term:
            return False
        # Append any new entries (overwrite conflicting)
        self.log = self.log[:prev_log_index + 1] + entries
        if leader_commit > self.commit_index:
            old_commit = self.commit_index
            self.commit_index = min(leader_commit, len(self.log) - 1)
            self._apply_entries(old_commit)
        return False
    
    xǁRaftNodeǁreceive_append_entries__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁRaftNodeǁreceive_append_entries__mutmut_1': xǁRaftNodeǁreceive_append_entries__mutmut_1, 
        'xǁRaftNodeǁreceive_append_entries__mutmut_2': xǁRaftNodeǁreceive_append_entries__mutmut_2, 
        'xǁRaftNodeǁreceive_append_entries__mutmut_3': xǁRaftNodeǁreceive_append_entries__mutmut_3, 
        'xǁRaftNodeǁreceive_append_entries__mutmut_4': xǁRaftNodeǁreceive_append_entries__mutmut_4, 
        'xǁRaftNodeǁreceive_append_entries__mutmut_5': xǁRaftNodeǁreceive_append_entries__mutmut_5, 
        'xǁRaftNodeǁreceive_append_entries__mutmut_6': xǁRaftNodeǁreceive_append_entries__mutmut_6, 
        'xǁRaftNodeǁreceive_append_entries__mutmut_7': xǁRaftNodeǁreceive_append_entries__mutmut_7, 
        'xǁRaftNodeǁreceive_append_entries__mutmut_8': xǁRaftNodeǁreceive_append_entries__mutmut_8, 
        'xǁRaftNodeǁreceive_append_entries__mutmut_9': xǁRaftNodeǁreceive_append_entries__mutmut_9, 
        'xǁRaftNodeǁreceive_append_entries__mutmut_10': xǁRaftNodeǁreceive_append_entries__mutmut_10, 
        'xǁRaftNodeǁreceive_append_entries__mutmut_11': xǁRaftNodeǁreceive_append_entries__mutmut_11, 
        'xǁRaftNodeǁreceive_append_entries__mutmut_12': xǁRaftNodeǁreceive_append_entries__mutmut_12, 
        'xǁRaftNodeǁreceive_append_entries__mutmut_13': xǁRaftNodeǁreceive_append_entries__mutmut_13, 
        'xǁRaftNodeǁreceive_append_entries__mutmut_14': xǁRaftNodeǁreceive_append_entries__mutmut_14, 
        'xǁRaftNodeǁreceive_append_entries__mutmut_15': xǁRaftNodeǁreceive_append_entries__mutmut_15, 
        'xǁRaftNodeǁreceive_append_entries__mutmut_16': xǁRaftNodeǁreceive_append_entries__mutmut_16, 
        'xǁRaftNodeǁreceive_append_entries__mutmut_17': xǁRaftNodeǁreceive_append_entries__mutmut_17, 
        'xǁRaftNodeǁreceive_append_entries__mutmut_18': xǁRaftNodeǁreceive_append_entries__mutmut_18, 
        'xǁRaftNodeǁreceive_append_entries__mutmut_19': xǁRaftNodeǁreceive_append_entries__mutmut_19, 
        'xǁRaftNodeǁreceive_append_entries__mutmut_20': xǁRaftNodeǁreceive_append_entries__mutmut_20, 
        'xǁRaftNodeǁreceive_append_entries__mutmut_21': xǁRaftNodeǁreceive_append_entries__mutmut_21, 
        'xǁRaftNodeǁreceive_append_entries__mutmut_22': xǁRaftNodeǁreceive_append_entries__mutmut_22, 
        'xǁRaftNodeǁreceive_append_entries__mutmut_23': xǁRaftNodeǁreceive_append_entries__mutmut_23, 
        'xǁRaftNodeǁreceive_append_entries__mutmut_24': xǁRaftNodeǁreceive_append_entries__mutmut_24, 
        'xǁRaftNodeǁreceive_append_entries__mutmut_25': xǁRaftNodeǁreceive_append_entries__mutmut_25, 
        'xǁRaftNodeǁreceive_append_entries__mutmut_26': xǁRaftNodeǁreceive_append_entries__mutmut_26, 
        'xǁRaftNodeǁreceive_append_entries__mutmut_27': xǁRaftNodeǁreceive_append_entries__mutmut_27, 
        'xǁRaftNodeǁreceive_append_entries__mutmut_28': xǁRaftNodeǁreceive_append_entries__mutmut_28, 
        'xǁRaftNodeǁreceive_append_entries__mutmut_29': xǁRaftNodeǁreceive_append_entries__mutmut_29
    }
    
    def receive_append_entries(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁRaftNodeǁreceive_append_entries__mutmut_orig"), object.__getattribute__(self, "xǁRaftNodeǁreceive_append_entries__mutmut_mutants"), args, kwargs, self)
        return result 
    
    receive_append_entries.__signature__ = _mutmut_signature(xǁRaftNodeǁreceive_append_entries__mutmut_orig)
    xǁRaftNodeǁreceive_append_entries__mutmut_orig.__name__ = 'xǁRaftNodeǁreceive_append_entries'

    def xǁRaftNodeǁreceive_request_vote__mutmut_orig(self, term: int, candidate_id: str, last_log_index: int, last_log_term: int) -> bool:
        if term < self.current_term:
            return False
        if term > self.current_term:
            self._become_follower(term=term)
        # Already voted for someone else
        if self.voted_for is not None and self.voted_for != candidate_id:
            return False
        # Section 5.4.1: candidate's log must be at least as up-to-date
        my_last_index = len(self.log) - 1
        my_last_term = self.log[my_last_index].term
        if last_log_term < my_last_term:
            return False
        if last_log_term == my_last_term and last_log_index < my_last_index:
            return False
        self.voted_for = candidate_id
        self.last_activity = datetime.now()
        return True

    def xǁRaftNodeǁreceive_request_vote__mutmut_1(self, term: int, candidate_id: str, last_log_index: int, last_log_term: int) -> bool:
        if term <= self.current_term:
            return False
        if term > self.current_term:
            self._become_follower(term=term)
        # Already voted for someone else
        if self.voted_for is not None and self.voted_for != candidate_id:
            return False
        # Section 5.4.1: candidate's log must be at least as up-to-date
        my_last_index = len(self.log) - 1
        my_last_term = self.log[my_last_index].term
        if last_log_term < my_last_term:
            return False
        if last_log_term == my_last_term and last_log_index < my_last_index:
            return False
        self.voted_for = candidate_id
        self.last_activity = datetime.now()
        return True

    def xǁRaftNodeǁreceive_request_vote__mutmut_2(self, term: int, candidate_id: str, last_log_index: int, last_log_term: int) -> bool:
        if term < self.current_term:
            return True
        if term > self.current_term:
            self._become_follower(term=term)
        # Already voted for someone else
        if self.voted_for is not None and self.voted_for != candidate_id:
            return False
        # Section 5.4.1: candidate's log must be at least as up-to-date
        my_last_index = len(self.log) - 1
        my_last_term = self.log[my_last_index].term
        if last_log_term < my_last_term:
            return False
        if last_log_term == my_last_term and last_log_index < my_last_index:
            return False
        self.voted_for = candidate_id
        self.last_activity = datetime.now()
        return True

    def xǁRaftNodeǁreceive_request_vote__mutmut_3(self, term: int, candidate_id: str, last_log_index: int, last_log_term: int) -> bool:
        if term < self.current_term:
            return False
        if term >= self.current_term:
            self._become_follower(term=term)
        # Already voted for someone else
        if self.voted_for is not None and self.voted_for != candidate_id:
            return False
        # Section 5.4.1: candidate's log must be at least as up-to-date
        my_last_index = len(self.log) - 1
        my_last_term = self.log[my_last_index].term
        if last_log_term < my_last_term:
            return False
        if last_log_term == my_last_term and last_log_index < my_last_index:
            return False
        self.voted_for = candidate_id
        self.last_activity = datetime.now()
        return True

    def xǁRaftNodeǁreceive_request_vote__mutmut_4(self, term: int, candidate_id: str, last_log_index: int, last_log_term: int) -> bool:
        if term < self.current_term:
            return False
        if term > self.current_term:
            self._become_follower(term=None)
        # Already voted for someone else
        if self.voted_for is not None and self.voted_for != candidate_id:
            return False
        # Section 5.4.1: candidate's log must be at least as up-to-date
        my_last_index = len(self.log) - 1
        my_last_term = self.log[my_last_index].term
        if last_log_term < my_last_term:
            return False
        if last_log_term == my_last_term and last_log_index < my_last_index:
            return False
        self.voted_for = candidate_id
        self.last_activity = datetime.now()
        return True

    def xǁRaftNodeǁreceive_request_vote__mutmut_5(self, term: int, candidate_id: str, last_log_index: int, last_log_term: int) -> bool:
        if term < self.current_term:
            return False
        if term > self.current_term:
            self._become_follower(term=term)
        # Already voted for someone else
        if self.voted_for is not None or self.voted_for != candidate_id:
            return False
        # Section 5.4.1: candidate's log must be at least as up-to-date
        my_last_index = len(self.log) - 1
        my_last_term = self.log[my_last_index].term
        if last_log_term < my_last_term:
            return False
        if last_log_term == my_last_term and last_log_index < my_last_index:
            return False
        self.voted_for = candidate_id
        self.last_activity = datetime.now()
        return True

    def xǁRaftNodeǁreceive_request_vote__mutmut_6(self, term: int, candidate_id: str, last_log_index: int, last_log_term: int) -> bool:
        if term < self.current_term:
            return False
        if term > self.current_term:
            self._become_follower(term=term)
        # Already voted for someone else
        if self.voted_for is None and self.voted_for != candidate_id:
            return False
        # Section 5.4.1: candidate's log must be at least as up-to-date
        my_last_index = len(self.log) - 1
        my_last_term = self.log[my_last_index].term
        if last_log_term < my_last_term:
            return False
        if last_log_term == my_last_term and last_log_index < my_last_index:
            return False
        self.voted_for = candidate_id
        self.last_activity = datetime.now()
        return True

    def xǁRaftNodeǁreceive_request_vote__mutmut_7(self, term: int, candidate_id: str, last_log_index: int, last_log_term: int) -> bool:
        if term < self.current_term:
            return False
        if term > self.current_term:
            self._become_follower(term=term)
        # Already voted for someone else
        if self.voted_for is not None and self.voted_for == candidate_id:
            return False
        # Section 5.4.1: candidate's log must be at least as up-to-date
        my_last_index = len(self.log) - 1
        my_last_term = self.log[my_last_index].term
        if last_log_term < my_last_term:
            return False
        if last_log_term == my_last_term and last_log_index < my_last_index:
            return False
        self.voted_for = candidate_id
        self.last_activity = datetime.now()
        return True

    def xǁRaftNodeǁreceive_request_vote__mutmut_8(self, term: int, candidate_id: str, last_log_index: int, last_log_term: int) -> bool:
        if term < self.current_term:
            return False
        if term > self.current_term:
            self._become_follower(term=term)
        # Already voted for someone else
        if self.voted_for is not None and self.voted_for != candidate_id:
            return True
        # Section 5.4.1: candidate's log must be at least as up-to-date
        my_last_index = len(self.log) - 1
        my_last_term = self.log[my_last_index].term
        if last_log_term < my_last_term:
            return False
        if last_log_term == my_last_term and last_log_index < my_last_index:
            return False
        self.voted_for = candidate_id
        self.last_activity = datetime.now()
        return True

    def xǁRaftNodeǁreceive_request_vote__mutmut_9(self, term: int, candidate_id: str, last_log_index: int, last_log_term: int) -> bool:
        if term < self.current_term:
            return False
        if term > self.current_term:
            self._become_follower(term=term)
        # Already voted for someone else
        if self.voted_for is not None and self.voted_for != candidate_id:
            return False
        # Section 5.4.1: candidate's log must be at least as up-to-date
        my_last_index = None
        my_last_term = self.log[my_last_index].term
        if last_log_term < my_last_term:
            return False
        if last_log_term == my_last_term and last_log_index < my_last_index:
            return False
        self.voted_for = candidate_id
        self.last_activity = datetime.now()
        return True

    def xǁRaftNodeǁreceive_request_vote__mutmut_10(self, term: int, candidate_id: str, last_log_index: int, last_log_term: int) -> bool:
        if term < self.current_term:
            return False
        if term > self.current_term:
            self._become_follower(term=term)
        # Already voted for someone else
        if self.voted_for is not None and self.voted_for != candidate_id:
            return False
        # Section 5.4.1: candidate's log must be at least as up-to-date
        my_last_index = len(self.log) + 1
        my_last_term = self.log[my_last_index].term
        if last_log_term < my_last_term:
            return False
        if last_log_term == my_last_term and last_log_index < my_last_index:
            return False
        self.voted_for = candidate_id
        self.last_activity = datetime.now()
        return True

    def xǁRaftNodeǁreceive_request_vote__mutmut_11(self, term: int, candidate_id: str, last_log_index: int, last_log_term: int) -> bool:
        if term < self.current_term:
            return False
        if term > self.current_term:
            self._become_follower(term=term)
        # Already voted for someone else
        if self.voted_for is not None and self.voted_for != candidate_id:
            return False
        # Section 5.4.1: candidate's log must be at least as up-to-date
        my_last_index = len(self.log) - 2
        my_last_term = self.log[my_last_index].term
        if last_log_term < my_last_term:
            return False
        if last_log_term == my_last_term and last_log_index < my_last_index:
            return False
        self.voted_for = candidate_id
        self.last_activity = datetime.now()
        return True

    def xǁRaftNodeǁreceive_request_vote__mutmut_12(self, term: int, candidate_id: str, last_log_index: int, last_log_term: int) -> bool:
        if term < self.current_term:
            return False
        if term > self.current_term:
            self._become_follower(term=term)
        # Already voted for someone else
        if self.voted_for is not None and self.voted_for != candidate_id:
            return False
        # Section 5.4.1: candidate's log must be at least as up-to-date
        my_last_index = len(self.log) - 1
        my_last_term = None
        if last_log_term < my_last_term:
            return False
        if last_log_term == my_last_term and last_log_index < my_last_index:
            return False
        self.voted_for = candidate_id
        self.last_activity = datetime.now()
        return True

    def xǁRaftNodeǁreceive_request_vote__mutmut_13(self, term: int, candidate_id: str, last_log_index: int, last_log_term: int) -> bool:
        if term < self.current_term:
            return False
        if term > self.current_term:
            self._become_follower(term=term)
        # Already voted for someone else
        if self.voted_for is not None and self.voted_for != candidate_id:
            return False
        # Section 5.4.1: candidate's log must be at least as up-to-date
        my_last_index = len(self.log) - 1
        my_last_term = self.log[my_last_index].term
        if last_log_term <= my_last_term:
            return False
        if last_log_term == my_last_term and last_log_index < my_last_index:
            return False
        self.voted_for = candidate_id
        self.last_activity = datetime.now()
        return True

    def xǁRaftNodeǁreceive_request_vote__mutmut_14(self, term: int, candidate_id: str, last_log_index: int, last_log_term: int) -> bool:
        if term < self.current_term:
            return False
        if term > self.current_term:
            self._become_follower(term=term)
        # Already voted for someone else
        if self.voted_for is not None and self.voted_for != candidate_id:
            return False
        # Section 5.4.1: candidate's log must be at least as up-to-date
        my_last_index = len(self.log) - 1
        my_last_term = self.log[my_last_index].term
        if last_log_term < my_last_term:
            return True
        if last_log_term == my_last_term and last_log_index < my_last_index:
            return False
        self.voted_for = candidate_id
        self.last_activity = datetime.now()
        return True

    def xǁRaftNodeǁreceive_request_vote__mutmut_15(self, term: int, candidate_id: str, last_log_index: int, last_log_term: int) -> bool:
        if term < self.current_term:
            return False
        if term > self.current_term:
            self._become_follower(term=term)
        # Already voted for someone else
        if self.voted_for is not None and self.voted_for != candidate_id:
            return False
        # Section 5.4.1: candidate's log must be at least as up-to-date
        my_last_index = len(self.log) - 1
        my_last_term = self.log[my_last_index].term
        if last_log_term < my_last_term:
            return False
        if last_log_term == my_last_term or last_log_index < my_last_index:
            return False
        self.voted_for = candidate_id
        self.last_activity = datetime.now()
        return True

    def xǁRaftNodeǁreceive_request_vote__mutmut_16(self, term: int, candidate_id: str, last_log_index: int, last_log_term: int) -> bool:
        if term < self.current_term:
            return False
        if term > self.current_term:
            self._become_follower(term=term)
        # Already voted for someone else
        if self.voted_for is not None and self.voted_for != candidate_id:
            return False
        # Section 5.4.1: candidate's log must be at least as up-to-date
        my_last_index = len(self.log) - 1
        my_last_term = self.log[my_last_index].term
        if last_log_term < my_last_term:
            return False
        if last_log_term != my_last_term and last_log_index < my_last_index:
            return False
        self.voted_for = candidate_id
        self.last_activity = datetime.now()
        return True

    def xǁRaftNodeǁreceive_request_vote__mutmut_17(self, term: int, candidate_id: str, last_log_index: int, last_log_term: int) -> bool:
        if term < self.current_term:
            return False
        if term > self.current_term:
            self._become_follower(term=term)
        # Already voted for someone else
        if self.voted_for is not None and self.voted_for != candidate_id:
            return False
        # Section 5.4.1: candidate's log must be at least as up-to-date
        my_last_index = len(self.log) - 1
        my_last_term = self.log[my_last_index].term
        if last_log_term < my_last_term:
            return False
        if last_log_term == my_last_term and last_log_index <= my_last_index:
            return False
        self.voted_for = candidate_id
        self.last_activity = datetime.now()
        return True

    def xǁRaftNodeǁreceive_request_vote__mutmut_18(self, term: int, candidate_id: str, last_log_index: int, last_log_term: int) -> bool:
        if term < self.current_term:
            return False
        if term > self.current_term:
            self._become_follower(term=term)
        # Already voted for someone else
        if self.voted_for is not None and self.voted_for != candidate_id:
            return False
        # Section 5.4.1: candidate's log must be at least as up-to-date
        my_last_index = len(self.log) - 1
        my_last_term = self.log[my_last_index].term
        if last_log_term < my_last_term:
            return False
        if last_log_term == my_last_term and last_log_index < my_last_index:
            return True
        self.voted_for = candidate_id
        self.last_activity = datetime.now()
        return True

    def xǁRaftNodeǁreceive_request_vote__mutmut_19(self, term: int, candidate_id: str, last_log_index: int, last_log_term: int) -> bool:
        if term < self.current_term:
            return False
        if term > self.current_term:
            self._become_follower(term=term)
        # Already voted for someone else
        if self.voted_for is not None and self.voted_for != candidate_id:
            return False
        # Section 5.4.1: candidate's log must be at least as up-to-date
        my_last_index = len(self.log) - 1
        my_last_term = self.log[my_last_index].term
        if last_log_term < my_last_term:
            return False
        if last_log_term == my_last_term and last_log_index < my_last_index:
            return False
        self.voted_for = None
        self.last_activity = datetime.now()
        return True

    def xǁRaftNodeǁreceive_request_vote__mutmut_20(self, term: int, candidate_id: str, last_log_index: int, last_log_term: int) -> bool:
        if term < self.current_term:
            return False
        if term > self.current_term:
            self._become_follower(term=term)
        # Already voted for someone else
        if self.voted_for is not None and self.voted_for != candidate_id:
            return False
        # Section 5.4.1: candidate's log must be at least as up-to-date
        my_last_index = len(self.log) - 1
        my_last_term = self.log[my_last_index].term
        if last_log_term < my_last_term:
            return False
        if last_log_term == my_last_term and last_log_index < my_last_index:
            return False
        self.voted_for = candidate_id
        self.last_activity = None
        return True

    def xǁRaftNodeǁreceive_request_vote__mutmut_21(self, term: int, candidate_id: str, last_log_index: int, last_log_term: int) -> bool:
        if term < self.current_term:
            return False
        if term > self.current_term:
            self._become_follower(term=term)
        # Already voted for someone else
        if self.voted_for is not None and self.voted_for != candidate_id:
            return False
        # Section 5.4.1: candidate's log must be at least as up-to-date
        my_last_index = len(self.log) - 1
        my_last_term = self.log[my_last_index].term
        if last_log_term < my_last_term:
            return False
        if last_log_term == my_last_term and last_log_index < my_last_index:
            return False
        self.voted_for = candidate_id
        self.last_activity = datetime.now()
        return False
    
    xǁRaftNodeǁreceive_request_vote__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁRaftNodeǁreceive_request_vote__mutmut_1': xǁRaftNodeǁreceive_request_vote__mutmut_1, 
        'xǁRaftNodeǁreceive_request_vote__mutmut_2': xǁRaftNodeǁreceive_request_vote__mutmut_2, 
        'xǁRaftNodeǁreceive_request_vote__mutmut_3': xǁRaftNodeǁreceive_request_vote__mutmut_3, 
        'xǁRaftNodeǁreceive_request_vote__mutmut_4': xǁRaftNodeǁreceive_request_vote__mutmut_4, 
        'xǁRaftNodeǁreceive_request_vote__mutmut_5': xǁRaftNodeǁreceive_request_vote__mutmut_5, 
        'xǁRaftNodeǁreceive_request_vote__mutmut_6': xǁRaftNodeǁreceive_request_vote__mutmut_6, 
        'xǁRaftNodeǁreceive_request_vote__mutmut_7': xǁRaftNodeǁreceive_request_vote__mutmut_7, 
        'xǁRaftNodeǁreceive_request_vote__mutmut_8': xǁRaftNodeǁreceive_request_vote__mutmut_8, 
        'xǁRaftNodeǁreceive_request_vote__mutmut_9': xǁRaftNodeǁreceive_request_vote__mutmut_9, 
        'xǁRaftNodeǁreceive_request_vote__mutmut_10': xǁRaftNodeǁreceive_request_vote__mutmut_10, 
        'xǁRaftNodeǁreceive_request_vote__mutmut_11': xǁRaftNodeǁreceive_request_vote__mutmut_11, 
        'xǁRaftNodeǁreceive_request_vote__mutmut_12': xǁRaftNodeǁreceive_request_vote__mutmut_12, 
        'xǁRaftNodeǁreceive_request_vote__mutmut_13': xǁRaftNodeǁreceive_request_vote__mutmut_13, 
        'xǁRaftNodeǁreceive_request_vote__mutmut_14': xǁRaftNodeǁreceive_request_vote__mutmut_14, 
        'xǁRaftNodeǁreceive_request_vote__mutmut_15': xǁRaftNodeǁreceive_request_vote__mutmut_15, 
        'xǁRaftNodeǁreceive_request_vote__mutmut_16': xǁRaftNodeǁreceive_request_vote__mutmut_16, 
        'xǁRaftNodeǁreceive_request_vote__mutmut_17': xǁRaftNodeǁreceive_request_vote__mutmut_17, 
        'xǁRaftNodeǁreceive_request_vote__mutmut_18': xǁRaftNodeǁreceive_request_vote__mutmut_18, 
        'xǁRaftNodeǁreceive_request_vote__mutmut_19': xǁRaftNodeǁreceive_request_vote__mutmut_19, 
        'xǁRaftNodeǁreceive_request_vote__mutmut_20': xǁRaftNodeǁreceive_request_vote__mutmut_20, 
        'xǁRaftNodeǁreceive_request_vote__mutmut_21': xǁRaftNodeǁreceive_request_vote__mutmut_21
    }
    
    def receive_request_vote(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁRaftNodeǁreceive_request_vote__mutmut_orig"), object.__getattribute__(self, "xǁRaftNodeǁreceive_request_vote__mutmut_mutants"), args, kwargs, self)
        return result 
    
    receive_request_vote.__signature__ = _mutmut_signature(xǁRaftNodeǁreceive_request_vote__mutmut_orig)
    xǁRaftNodeǁreceive_request_vote__mutmut_orig.__name__ = 'xǁRaftNodeǁreceive_request_vote'

    # ------------------------------------------------------------------
    # Timeouts
    # ------------------------------------------------------------------
    def xǁRaftNodeǁcheck_timeout__mutmut_orig(self) -> bool:
        now = datetime.now()
        elapsed_ms = (now - self.last_activity).total_seconds() * 1000
        if self.state == RaftState.LEADER:
            if (now - self.last_heartbeat).total_seconds() * 1000 > self.config.heartbeat_interval:
                self._send_heartbeats()
            return False
        else:
            if elapsed_ms > self.election_timeout:
                return self.start_election()
        return False

    # ------------------------------------------------------------------
    # Timeouts
    # ------------------------------------------------------------------
    def xǁRaftNodeǁcheck_timeout__mutmut_1(self) -> bool:
        now = None
        elapsed_ms = (now - self.last_activity).total_seconds() * 1000
        if self.state == RaftState.LEADER:
            if (now - self.last_heartbeat).total_seconds() * 1000 > self.config.heartbeat_interval:
                self._send_heartbeats()
            return False
        else:
            if elapsed_ms > self.election_timeout:
                return self.start_election()
        return False

    # ------------------------------------------------------------------
    # Timeouts
    # ------------------------------------------------------------------
    def xǁRaftNodeǁcheck_timeout__mutmut_2(self) -> bool:
        now = datetime.now()
        elapsed_ms = None
        if self.state == RaftState.LEADER:
            if (now - self.last_heartbeat).total_seconds() * 1000 > self.config.heartbeat_interval:
                self._send_heartbeats()
            return False
        else:
            if elapsed_ms > self.election_timeout:
                return self.start_election()
        return False

    # ------------------------------------------------------------------
    # Timeouts
    # ------------------------------------------------------------------
    def xǁRaftNodeǁcheck_timeout__mutmut_3(self) -> bool:
        now = datetime.now()
        elapsed_ms = (now - self.last_activity).total_seconds() / 1000
        if self.state == RaftState.LEADER:
            if (now - self.last_heartbeat).total_seconds() * 1000 > self.config.heartbeat_interval:
                self._send_heartbeats()
            return False
        else:
            if elapsed_ms > self.election_timeout:
                return self.start_election()
        return False

    # ------------------------------------------------------------------
    # Timeouts
    # ------------------------------------------------------------------
    def xǁRaftNodeǁcheck_timeout__mutmut_4(self) -> bool:
        now = datetime.now()
        elapsed_ms = (now + self.last_activity).total_seconds() * 1000
        if self.state == RaftState.LEADER:
            if (now - self.last_heartbeat).total_seconds() * 1000 > self.config.heartbeat_interval:
                self._send_heartbeats()
            return False
        else:
            if elapsed_ms > self.election_timeout:
                return self.start_election()
        return False

    # ------------------------------------------------------------------
    # Timeouts
    # ------------------------------------------------------------------
    def xǁRaftNodeǁcheck_timeout__mutmut_5(self) -> bool:
        now = datetime.now()
        elapsed_ms = (now - self.last_activity).total_seconds() * 1001
        if self.state == RaftState.LEADER:
            if (now - self.last_heartbeat).total_seconds() * 1000 > self.config.heartbeat_interval:
                self._send_heartbeats()
            return False
        else:
            if elapsed_ms > self.election_timeout:
                return self.start_election()
        return False

    # ------------------------------------------------------------------
    # Timeouts
    # ------------------------------------------------------------------
    def xǁRaftNodeǁcheck_timeout__mutmut_6(self) -> bool:
        now = datetime.now()
        elapsed_ms = (now - self.last_activity).total_seconds() * 1000
        if self.state != RaftState.LEADER:
            if (now - self.last_heartbeat).total_seconds() * 1000 > self.config.heartbeat_interval:
                self._send_heartbeats()
            return False
        else:
            if elapsed_ms > self.election_timeout:
                return self.start_election()
        return False

    # ------------------------------------------------------------------
    # Timeouts
    # ------------------------------------------------------------------
    def xǁRaftNodeǁcheck_timeout__mutmut_7(self) -> bool:
        now = datetime.now()
        elapsed_ms = (now - self.last_activity).total_seconds() * 1000
        if self.state == RaftState.LEADER:
            if (now - self.last_heartbeat).total_seconds() / 1000 > self.config.heartbeat_interval:
                self._send_heartbeats()
            return False
        else:
            if elapsed_ms > self.election_timeout:
                return self.start_election()
        return False

    # ------------------------------------------------------------------
    # Timeouts
    # ------------------------------------------------------------------
    def xǁRaftNodeǁcheck_timeout__mutmut_8(self) -> bool:
        now = datetime.now()
        elapsed_ms = (now - self.last_activity).total_seconds() * 1000
        if self.state == RaftState.LEADER:
            if (now + self.last_heartbeat).total_seconds() * 1000 > self.config.heartbeat_interval:
                self._send_heartbeats()
            return False
        else:
            if elapsed_ms > self.election_timeout:
                return self.start_election()
        return False

    # ------------------------------------------------------------------
    # Timeouts
    # ------------------------------------------------------------------
    def xǁRaftNodeǁcheck_timeout__mutmut_9(self) -> bool:
        now = datetime.now()
        elapsed_ms = (now - self.last_activity).total_seconds() * 1000
        if self.state == RaftState.LEADER:
            if (now - self.last_heartbeat).total_seconds() * 1001 > self.config.heartbeat_interval:
                self._send_heartbeats()
            return False
        else:
            if elapsed_ms > self.election_timeout:
                return self.start_election()
        return False

    # ------------------------------------------------------------------
    # Timeouts
    # ------------------------------------------------------------------
    def xǁRaftNodeǁcheck_timeout__mutmut_10(self) -> bool:
        now = datetime.now()
        elapsed_ms = (now - self.last_activity).total_seconds() * 1000
        if self.state == RaftState.LEADER:
            if (now - self.last_heartbeat).total_seconds() * 1000 >= self.config.heartbeat_interval:
                self._send_heartbeats()
            return False
        else:
            if elapsed_ms > self.election_timeout:
                return self.start_election()
        return False

    # ------------------------------------------------------------------
    # Timeouts
    # ------------------------------------------------------------------
    def xǁRaftNodeǁcheck_timeout__mutmut_11(self) -> bool:
        now = datetime.now()
        elapsed_ms = (now - self.last_activity).total_seconds() * 1000
        if self.state == RaftState.LEADER:
            if (now - self.last_heartbeat).total_seconds() * 1000 > self.config.heartbeat_interval:
                self._send_heartbeats()
            return True
        else:
            if elapsed_ms > self.election_timeout:
                return self.start_election()
        return False

    # ------------------------------------------------------------------
    # Timeouts
    # ------------------------------------------------------------------
    def xǁRaftNodeǁcheck_timeout__mutmut_12(self) -> bool:
        now = datetime.now()
        elapsed_ms = (now - self.last_activity).total_seconds() * 1000
        if self.state == RaftState.LEADER:
            if (now - self.last_heartbeat).total_seconds() * 1000 > self.config.heartbeat_interval:
                self._send_heartbeats()
            return False
        else:
            if elapsed_ms >= self.election_timeout:
                return self.start_election()
        return False

    # ------------------------------------------------------------------
    # Timeouts
    # ------------------------------------------------------------------
    def xǁRaftNodeǁcheck_timeout__mutmut_13(self) -> bool:
        now = datetime.now()
        elapsed_ms = (now - self.last_activity).total_seconds() * 1000
        if self.state == RaftState.LEADER:
            if (now - self.last_heartbeat).total_seconds() * 1000 > self.config.heartbeat_interval:
                self._send_heartbeats()
            return False
        else:
            if elapsed_ms > self.election_timeout:
                return self.start_election()
        return True
    
    xǁRaftNodeǁcheck_timeout__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁRaftNodeǁcheck_timeout__mutmut_1': xǁRaftNodeǁcheck_timeout__mutmut_1, 
        'xǁRaftNodeǁcheck_timeout__mutmut_2': xǁRaftNodeǁcheck_timeout__mutmut_2, 
        'xǁRaftNodeǁcheck_timeout__mutmut_3': xǁRaftNodeǁcheck_timeout__mutmut_3, 
        'xǁRaftNodeǁcheck_timeout__mutmut_4': xǁRaftNodeǁcheck_timeout__mutmut_4, 
        'xǁRaftNodeǁcheck_timeout__mutmut_5': xǁRaftNodeǁcheck_timeout__mutmut_5, 
        'xǁRaftNodeǁcheck_timeout__mutmut_6': xǁRaftNodeǁcheck_timeout__mutmut_6, 
        'xǁRaftNodeǁcheck_timeout__mutmut_7': xǁRaftNodeǁcheck_timeout__mutmut_7, 
        'xǁRaftNodeǁcheck_timeout__mutmut_8': xǁRaftNodeǁcheck_timeout__mutmut_8, 
        'xǁRaftNodeǁcheck_timeout__mutmut_9': xǁRaftNodeǁcheck_timeout__mutmut_9, 
        'xǁRaftNodeǁcheck_timeout__mutmut_10': xǁRaftNodeǁcheck_timeout__mutmut_10, 
        'xǁRaftNodeǁcheck_timeout__mutmut_11': xǁRaftNodeǁcheck_timeout__mutmut_11, 
        'xǁRaftNodeǁcheck_timeout__mutmut_12': xǁRaftNodeǁcheck_timeout__mutmut_12, 
        'xǁRaftNodeǁcheck_timeout__mutmut_13': xǁRaftNodeǁcheck_timeout__mutmut_13
    }
    
    def check_timeout(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁRaftNodeǁcheck_timeout__mutmut_orig"), object.__getattribute__(self, "xǁRaftNodeǁcheck_timeout__mutmut_mutants"), args, kwargs, self)
        return result 
    
    check_timeout.__signature__ = _mutmut_signature(xǁRaftNodeǁcheck_timeout__mutmut_orig)
    xǁRaftNodeǁcheck_timeout__mutmut_orig.__name__ = 'xǁRaftNodeǁcheck_timeout'

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------
    def xǁRaftNodeǁget_status__mutmut_orig(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "state": self.state.value,
            "term": self.current_term,
            "log_length": len(self.log),
            "commit_index": self.commit_index,
            "last_applied": self.last_applied,
            "voted_for": self.voted_for,
        }

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------
    def xǁRaftNodeǁget_status__mutmut_1(self) -> Dict[str, Any]:
        return {
            "XXnode_idXX": self.node_id,
            "state": self.state.value,
            "term": self.current_term,
            "log_length": len(self.log),
            "commit_index": self.commit_index,
            "last_applied": self.last_applied,
            "voted_for": self.voted_for,
        }

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------
    def xǁRaftNodeǁget_status__mutmut_2(self) -> Dict[str, Any]:
        return {
            "NODE_ID": self.node_id,
            "state": self.state.value,
            "term": self.current_term,
            "log_length": len(self.log),
            "commit_index": self.commit_index,
            "last_applied": self.last_applied,
            "voted_for": self.voted_for,
        }

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------
    def xǁRaftNodeǁget_status__mutmut_3(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "XXstateXX": self.state.value,
            "term": self.current_term,
            "log_length": len(self.log),
            "commit_index": self.commit_index,
            "last_applied": self.last_applied,
            "voted_for": self.voted_for,
        }

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------
    def xǁRaftNodeǁget_status__mutmut_4(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "STATE": self.state.value,
            "term": self.current_term,
            "log_length": len(self.log),
            "commit_index": self.commit_index,
            "last_applied": self.last_applied,
            "voted_for": self.voted_for,
        }

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------
    def xǁRaftNodeǁget_status__mutmut_5(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "state": self.state.value,
            "XXtermXX": self.current_term,
            "log_length": len(self.log),
            "commit_index": self.commit_index,
            "last_applied": self.last_applied,
            "voted_for": self.voted_for,
        }

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------
    def xǁRaftNodeǁget_status__mutmut_6(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "state": self.state.value,
            "TERM": self.current_term,
            "log_length": len(self.log),
            "commit_index": self.commit_index,
            "last_applied": self.last_applied,
            "voted_for": self.voted_for,
        }

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------
    def xǁRaftNodeǁget_status__mutmut_7(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "state": self.state.value,
            "term": self.current_term,
            "XXlog_lengthXX": len(self.log),
            "commit_index": self.commit_index,
            "last_applied": self.last_applied,
            "voted_for": self.voted_for,
        }

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------
    def xǁRaftNodeǁget_status__mutmut_8(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "state": self.state.value,
            "term": self.current_term,
            "LOG_LENGTH": len(self.log),
            "commit_index": self.commit_index,
            "last_applied": self.last_applied,
            "voted_for": self.voted_for,
        }

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------
    def xǁRaftNodeǁget_status__mutmut_9(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "state": self.state.value,
            "term": self.current_term,
            "log_length": len(self.log),
            "XXcommit_indexXX": self.commit_index,
            "last_applied": self.last_applied,
            "voted_for": self.voted_for,
        }

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------
    def xǁRaftNodeǁget_status__mutmut_10(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "state": self.state.value,
            "term": self.current_term,
            "log_length": len(self.log),
            "COMMIT_INDEX": self.commit_index,
            "last_applied": self.last_applied,
            "voted_for": self.voted_for,
        }

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------
    def xǁRaftNodeǁget_status__mutmut_11(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "state": self.state.value,
            "term": self.current_term,
            "log_length": len(self.log),
            "commit_index": self.commit_index,
            "XXlast_appliedXX": self.last_applied,
            "voted_for": self.voted_for,
        }

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------
    def xǁRaftNodeǁget_status__mutmut_12(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "state": self.state.value,
            "term": self.current_term,
            "log_length": len(self.log),
            "commit_index": self.commit_index,
            "LAST_APPLIED": self.last_applied,
            "voted_for": self.voted_for,
        }

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------
    def xǁRaftNodeǁget_status__mutmut_13(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "state": self.state.value,
            "term": self.current_term,
            "log_length": len(self.log),
            "commit_index": self.commit_index,
            "last_applied": self.last_applied,
            "XXvoted_forXX": self.voted_for,
        }

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------
    def xǁRaftNodeǁget_status__mutmut_14(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "state": self.state.value,
            "term": self.current_term,
            "log_length": len(self.log),
            "commit_index": self.commit_index,
            "last_applied": self.last_applied,
            "VOTED_FOR": self.voted_for,
        }
    
    xǁRaftNodeǁget_status__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁRaftNodeǁget_status__mutmut_1': xǁRaftNodeǁget_status__mutmut_1, 
        'xǁRaftNodeǁget_status__mutmut_2': xǁRaftNodeǁget_status__mutmut_2, 
        'xǁRaftNodeǁget_status__mutmut_3': xǁRaftNodeǁget_status__mutmut_3, 
        'xǁRaftNodeǁget_status__mutmut_4': xǁRaftNodeǁget_status__mutmut_4, 
        'xǁRaftNodeǁget_status__mutmut_5': xǁRaftNodeǁget_status__mutmut_5, 
        'xǁRaftNodeǁget_status__mutmut_6': xǁRaftNodeǁget_status__mutmut_6, 
        'xǁRaftNodeǁget_status__mutmut_7': xǁRaftNodeǁget_status__mutmut_7, 
        'xǁRaftNodeǁget_status__mutmut_8': xǁRaftNodeǁget_status__mutmut_8, 
        'xǁRaftNodeǁget_status__mutmut_9': xǁRaftNodeǁget_status__mutmut_9, 
        'xǁRaftNodeǁget_status__mutmut_10': xǁRaftNodeǁget_status__mutmut_10, 
        'xǁRaftNodeǁget_status__mutmut_11': xǁRaftNodeǁget_status__mutmut_11, 
        'xǁRaftNodeǁget_status__mutmut_12': xǁRaftNodeǁget_status__mutmut_12, 
        'xǁRaftNodeǁget_status__mutmut_13': xǁRaftNodeǁget_status__mutmut_13, 
        'xǁRaftNodeǁget_status__mutmut_14': xǁRaftNodeǁget_status__mutmut_14
    }
    
    def get_status(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁRaftNodeǁget_status__mutmut_orig"), object.__getattribute__(self, "xǁRaftNodeǁget_status__mutmut_mutants"), args, kwargs, self)
        return result 
    
    get_status.__signature__ = _mutmut_signature(xǁRaftNodeǁget_status__mutmut_orig)
    xǁRaftNodeǁget_status__mutmut_orig.__name__ = 'xǁRaftNodeǁget_status'


class RaftCluster:
    """Cluster orchestration for in-process tests."""

    def xǁRaftClusterǁ__init____mutmut_orig(self, node_ids: List[str], config: Optional[RaftConfig] = None):
        self.config = config or RaftConfig()
        self.nodes: Dict[str, RaftNode] = {
            nid: RaftNode(nid, node_ids, self.config, rng=random.Random(100 + i))
            for i, nid in enumerate(node_ids)
        }

    def xǁRaftClusterǁ__init____mutmut_1(self, node_ids: List[str], config: Optional[RaftConfig] = None):
        self.config = None
        self.nodes: Dict[str, RaftNode] = {
            nid: RaftNode(nid, node_ids, self.config, rng=random.Random(100 + i))
            for i, nid in enumerate(node_ids)
        }

    def xǁRaftClusterǁ__init____mutmut_2(self, node_ids: List[str], config: Optional[RaftConfig] = None):
        self.config = config and RaftConfig()
        self.nodes: Dict[str, RaftNode] = {
            nid: RaftNode(nid, node_ids, self.config, rng=random.Random(100 + i))
            for i, nid in enumerate(node_ids)
        }

    def xǁRaftClusterǁ__init____mutmut_3(self, node_ids: List[str], config: Optional[RaftConfig] = None):
        self.config = config or RaftConfig()
        self.nodes: Dict[str, RaftNode] = None

    def xǁRaftClusterǁ__init____mutmut_4(self, node_ids: List[str], config: Optional[RaftConfig] = None):
        self.config = config or RaftConfig()
        self.nodes: Dict[str, RaftNode] = {
            nid: RaftNode(None, node_ids, self.config, rng=random.Random(100 + i))
            for i, nid in enumerate(node_ids)
        }

    def xǁRaftClusterǁ__init____mutmut_5(self, node_ids: List[str], config: Optional[RaftConfig] = None):
        self.config = config or RaftConfig()
        self.nodes: Dict[str, RaftNode] = {
            nid: RaftNode(nid, None, self.config, rng=random.Random(100 + i))
            for i, nid in enumerate(node_ids)
        }

    def xǁRaftClusterǁ__init____mutmut_6(self, node_ids: List[str], config: Optional[RaftConfig] = None):
        self.config = config or RaftConfig()
        self.nodes: Dict[str, RaftNode] = {
            nid: RaftNode(nid, node_ids, None, rng=random.Random(100 + i))
            for i, nid in enumerate(node_ids)
        }

    def xǁRaftClusterǁ__init____mutmut_7(self, node_ids: List[str], config: Optional[RaftConfig] = None):
        self.config = config or RaftConfig()
        self.nodes: Dict[str, RaftNode] = {
            nid: RaftNode(nid, node_ids, self.config, rng=None)
            for i, nid in enumerate(node_ids)
        }

    def xǁRaftClusterǁ__init____mutmut_8(self, node_ids: List[str], config: Optional[RaftConfig] = None):
        self.config = config or RaftConfig()
        self.nodes: Dict[str, RaftNode] = {
            nid: RaftNode(node_ids, self.config, rng=random.Random(100 + i))
            for i, nid in enumerate(node_ids)
        }

    def xǁRaftClusterǁ__init____mutmut_9(self, node_ids: List[str], config: Optional[RaftConfig] = None):
        self.config = config or RaftConfig()
        self.nodes: Dict[str, RaftNode] = {
            nid: RaftNode(nid, self.config, rng=random.Random(100 + i))
            for i, nid in enumerate(node_ids)
        }

    def xǁRaftClusterǁ__init____mutmut_10(self, node_ids: List[str], config: Optional[RaftConfig] = None):
        self.config = config or RaftConfig()
        self.nodes: Dict[str, RaftNode] = {
            nid: RaftNode(nid, node_ids, rng=random.Random(100 + i))
            for i, nid in enumerate(node_ids)
        }

    def xǁRaftClusterǁ__init____mutmut_11(self, node_ids: List[str], config: Optional[RaftConfig] = None):
        self.config = config or RaftConfig()
        self.nodes: Dict[str, RaftNode] = {
            nid: RaftNode(nid, node_ids, self.config, )
            for i, nid in enumerate(node_ids)
        }

    def xǁRaftClusterǁ__init____mutmut_12(self, node_ids: List[str], config: Optional[RaftConfig] = None):
        self.config = config or RaftConfig()
        self.nodes: Dict[str, RaftNode] = {
            nid: RaftNode(nid, node_ids, self.config, rng=random.Random(None))
            for i, nid in enumerate(node_ids)
        }

    def xǁRaftClusterǁ__init____mutmut_13(self, node_ids: List[str], config: Optional[RaftConfig] = None):
        self.config = config or RaftConfig()
        self.nodes: Dict[str, RaftNode] = {
            nid: RaftNode(nid, node_ids, self.config, rng=random.Random(100 - i))
            for i, nid in enumerate(node_ids)
        }

    def xǁRaftClusterǁ__init____mutmut_14(self, node_ids: List[str], config: Optional[RaftConfig] = None):
        self.config = config or RaftConfig()
        self.nodes: Dict[str, RaftNode] = {
            nid: RaftNode(nid, node_ids, self.config, rng=random.Random(101 + i))
            for i, nid in enumerate(node_ids)
        }

    def xǁRaftClusterǁ__init____mutmut_15(self, node_ids: List[str], config: Optional[RaftConfig] = None):
        self.config = config or RaftConfig()
        self.nodes: Dict[str, RaftNode] = {
            nid: RaftNode(nid, node_ids, self.config, rng=random.Random(100 + i))
            for i, nid in enumerate(None)
        }
    
    xǁRaftClusterǁ__init____mutmut_mutants : ClassVar[MutantDict] = {
    'xǁRaftClusterǁ__init____mutmut_1': xǁRaftClusterǁ__init____mutmut_1, 
        'xǁRaftClusterǁ__init____mutmut_2': xǁRaftClusterǁ__init____mutmut_2, 
        'xǁRaftClusterǁ__init____mutmut_3': xǁRaftClusterǁ__init____mutmut_3, 
        'xǁRaftClusterǁ__init____mutmut_4': xǁRaftClusterǁ__init____mutmut_4, 
        'xǁRaftClusterǁ__init____mutmut_5': xǁRaftClusterǁ__init____mutmut_5, 
        'xǁRaftClusterǁ__init____mutmut_6': xǁRaftClusterǁ__init____mutmut_6, 
        'xǁRaftClusterǁ__init____mutmut_7': xǁRaftClusterǁ__init____mutmut_7, 
        'xǁRaftClusterǁ__init____mutmut_8': xǁRaftClusterǁ__init____mutmut_8, 
        'xǁRaftClusterǁ__init____mutmut_9': xǁRaftClusterǁ__init____mutmut_9, 
        'xǁRaftClusterǁ__init____mutmut_10': xǁRaftClusterǁ__init____mutmut_10, 
        'xǁRaftClusterǁ__init____mutmut_11': xǁRaftClusterǁ__init____mutmut_11, 
        'xǁRaftClusterǁ__init____mutmut_12': xǁRaftClusterǁ__init____mutmut_12, 
        'xǁRaftClusterǁ__init____mutmut_13': xǁRaftClusterǁ__init____mutmut_13, 
        'xǁRaftClusterǁ__init____mutmut_14': xǁRaftClusterǁ__init____mutmut_14, 
        'xǁRaftClusterǁ__init____mutmut_15': xǁRaftClusterǁ__init____mutmut_15
    }
    
    def __init__(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁRaftClusterǁ__init____mutmut_orig"), object.__getattribute__(self, "xǁRaftClusterǁ__init____mutmut_mutants"), args, kwargs, self)
        return result 
    
    __init__.__signature__ = _mutmut_signature(xǁRaftClusterǁ__init____mutmut_orig)
    xǁRaftClusterǁ__init____mutmut_orig.__name__ = 'xǁRaftClusterǁ__init__'

    def xǁRaftClusterǁget_leader__mutmut_orig(self) -> Optional[str]:
        for nid, node in self.nodes.items():
            if node.state == RaftState.LEADER:
                return nid
        return None

    def xǁRaftClusterǁget_leader__mutmut_1(self) -> Optional[str]:
        for nid, node in self.nodes.items():
            if node.state != RaftState.LEADER:
                return nid
        return None
    
    xǁRaftClusterǁget_leader__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁRaftClusterǁget_leader__mutmut_1': xǁRaftClusterǁget_leader__mutmut_1
    }
    
    def get_leader(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁRaftClusterǁget_leader__mutmut_orig"), object.__getattribute__(self, "xǁRaftClusterǁget_leader__mutmut_mutants"), args, kwargs, self)
        return result 
    
    get_leader.__signature__ = _mutmut_signature(xǁRaftClusterǁget_leader__mutmut_orig)
    xǁRaftClusterǁget_leader__mutmut_orig.__name__ = 'xǁRaftClusterǁget_leader'

    def xǁRaftClusterǁadd_command__mutmut_orig(self, command: Any) -> bool:
        leader_id = self.get_leader()
        if not leader_id:
            return False
        return self.nodes[leader_id].append_entry(command)

    def xǁRaftClusterǁadd_command__mutmut_1(self, command: Any) -> bool:
        leader_id = None
        if not leader_id:
            return False
        return self.nodes[leader_id].append_entry(command)

    def xǁRaftClusterǁadd_command__mutmut_2(self, command: Any) -> bool:
        leader_id = self.get_leader()
        if leader_id:
            return False
        return self.nodes[leader_id].append_entry(command)

    def xǁRaftClusterǁadd_command__mutmut_3(self, command: Any) -> bool:
        leader_id = self.get_leader()
        if not leader_id:
            return True
        return self.nodes[leader_id].append_entry(command)

    def xǁRaftClusterǁadd_command__mutmut_4(self, command: Any) -> bool:
        leader_id = self.get_leader()
        if not leader_id:
            return False
        return self.nodes[leader_id].append_entry(None)
    
    xǁRaftClusterǁadd_command__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁRaftClusterǁadd_command__mutmut_1': xǁRaftClusterǁadd_command__mutmut_1, 
        'xǁRaftClusterǁadd_command__mutmut_2': xǁRaftClusterǁadd_command__mutmut_2, 
        'xǁRaftClusterǁadd_command__mutmut_3': xǁRaftClusterǁadd_command__mutmut_3, 
        'xǁRaftClusterǁadd_command__mutmut_4': xǁRaftClusterǁadd_command__mutmut_4
    }
    
    def add_command(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁRaftClusterǁadd_command__mutmut_orig"), object.__getattribute__(self, "xǁRaftClusterǁadd_command__mutmut_mutants"), args, kwargs, self)
        return result 
    
    add_command.__signature__ = _mutmut_signature(xǁRaftClusterǁadd_command__mutmut_orig)
    xǁRaftClusterǁadd_command__mutmut_orig.__name__ = 'xǁRaftClusterǁadd_command'

    def simulate_tick(self):
        for node in self.nodes.values():
            node.check_timeout()

    def status(self) -> Dict[str, Dict[str, Any]]:
        return {nid: node.get_status() for nid, node in self.nodes.items()}

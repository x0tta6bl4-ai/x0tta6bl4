# Technical Ticket: Refactor SwarmConsensusManager → ConsensusEngine

**Ticket ID:** SWARM-001  
**Priority:** P0 (Blocker)  
**Status:** Open  
**Created:** 2026-02-23  
**Assignee:** TBD  
**Estimated Effort:** 2-3 days  

---

## Problem Statement

The current implementation has **two parallel consensus mechanisms** that create architectural issues:

### 1. Duplicate Consensus Engines

- [`ConsensusEngine`](src/swarm/consensus.py:184) — full-featured engine with voting, timeouts, callbacks
- [`SwarmConsensusManager`](src/swarm/consensus_integration.py:103) — wrapper that doesn't add value

### 2. Broken Raft Semantics

`SwarmConsensusManager._raft_decide()` creates a **new RaftNode instance on every decision**:

```python
# src/swarm/consensus_integration.py:335-360
async def _raft_decide(self, topic: str, proposals: List[Any], timeout: float) -> Any:
    from .consensus import RaftNode
    
    peer_ids = {aid for aid in self.agents if aid != self.node_id}
    raft = RaftNode(  # ← NEW INSTANCE EVERY TIME!
        node_id=self.node_id,
        peers=peer_ids,
    )
    
    await asyncio.sleep(0.5)  # Simplified
    # ...
```

**Why this breaks Raft:**
- RaftNode is stateful (term, log, state, voted_for)
- Creating new instance resets to FOLLOWER state
- Leader election never works properly
- Log replication impossible

### 3. Circular Dependency

```
SwarmIntelligence
    └── SwarmConsensusManager
            └── ConsensusEngine (via _simple_engine)
            └── RaftNode (created fresh each time)
            └── PaxosNode (lazy init)
            └── PBFTNode (lazy init)
```

---

## Impact

| Impact Area | Severity |
|-------------|----------|
| Raft consensus | **Broken** — cannot achieve distributed consensus |
| Code maintainability | **High** — two ways to do the same thing |
| Performance | **Medium** — unnecessary object creation |
| Testing | **High** — tests pass but system doesn't work |

---

## Proposed Solution

### Option A: Remove SwarmConsensusManager (Recommended)

1. **Delete** `src/swarm/consensus_integration.py`
2. **Extend** `ConsensusEngine` to support RAFT/PBFT modes
3. **Update** `SwarmIntelligence` to use `ConsensusEngine` directly

**Benefits:**
- Single source of truth for consensus
- RaftNode instances are properly managed
- Simpler architecture

**Code changes:**

```python
# src/swarm/consensus.py — add RAFT support

class ConsensusAlgorithm(str, Enum):
    # ... existing ...
    RAFT = "raft"
    PBFT = "pbft"

class ConsensusEngine:
    def __init__(self, ...):
        # ... existing ...
        self._raft_node: Optional[RaftNode] = None
        self._pbft_node: Optional[PBFTNode] = None
    
    def _initialize_raft(self, node_id: str, peers: Set[str]) -> None:
        """Initialize Raft node (once, reused across decisions)."""
        if self._raft_node is None:
            self._raft_node = RaftNode(node_id=node_id, peers=peers)
    
    async def _evaluate_raft(self, decision: Decision) -> ConsensusResult:
        """Evaluate using Raft consensus."""
        # Use existing _raft_node instance
        ...
```

```python
# src/swarm/intelligence.py — simplified

class SwarmIntelligence:
    def __init__(self, ...):
        # Replace SwarmConsensusManager with ConsensusEngine
        self._consensus_engine = ConsensusEngine(
            default_algorithm=ConsensusAlgorithm.RAFT,
        )
    
    async def initialize(self) -> None:
        # Initialize Raft once
        self._consensus_engine._initialize_raft(
            node_id=self.node_id,
            peers=self.peers,
        )
        await self._consensus_engine.start()
```

### Option B: Fix SwarmConsensusManager (Not Recommended)

Keep the wrapper but fix RaftNode lifecycle:

```python
class SwarmConsensusManager:
    def __init__(self, ...):
        self._raft_node: Optional[RaftNode] = None  # Reuse instance
    
    def _initialize_raft(self) -> None:
        if self._raft_node is None:
            peer_ids = {aid for aid in self.agents if aid != self.node_id}
            self._raft_node = RaftNode(node_id=self.node_id, peers=peer_ids)
```

**Drawbacks:**
- Still maintains two consensus systems
- More complex
- Doesn't address the fundamental duplication

---

## Acceptance Criteria

- [ ] `SwarmConsensusManager` removed or significantly refactored
- [ ] RaftNode instance created once and reused
- [ ] All existing tests pass
- [ ] New test: Raft leader election works across multiple decisions
- [ ] New test: Log replication works (entries persist across decisions)
- [ ] Documentation updated

---

## Related Issues

- #2: Network communication layer missing
- #9: No distributed tests
- #13: O(n²) message complexity

---

## References

- [Raft Paper](https://raft.github.io/raft.pdf)
- [`src/swarm/consensus.py`](src/swarm/consensus.py) — ConsensusEngine implementation
- [`src/swarm/consensus_integration.py`](src/swarm/consensus_integration.py) — Current SwarmConsensusManager
- [`src/swarm/intelligence.py`](src/swarm/intelligence.py) — SwarmIntelligence class

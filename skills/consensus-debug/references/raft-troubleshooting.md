# Raft Troubleshooting Guide

## Architecture

```
src/consensus/
├── raft_production.py    # Main Raft implementation (RaftNode, RaftLog, RaftStorage)
├── raft_config.py        # Configuration
└── ...

tests/unit/consensus/
└── test_raft_snapshots.py  # Snapshot create/load/compress tests
```

## Snapshot Format

**CRITICAL**: Snapshots use JSON format (migrated from pickle in Feb 2026 for RCE safety).

```
{snapshot_dir}/snapshot_{index:010d}.json      # uncompressed
{snapshot_dir}/snapshot_{index:010d}.json.gz   # compressed
```

Old `.pkl` format is GONE. Any test or code expecting `.pkl` will fail.

## RaftStorage API

```python
storage = RaftStorage(snapshot_dir=Path("/tmp/raft-snapshots"))

# Save snapshot
await storage.save_snapshot(index=42, term=3, state={"key": "value"})

# Load latest snapshot
snap = storage.load_snapshot()  # returns None if no snapshot

# List all snapshots
snaps = storage.list_snapshots()  # sorted by index
```

## RaftNode State Machine

```
FOLLOWER  →  CANDIDATE  →  LEADER
    ↑              ↓
    └──────────────┘  (lost election)
```

Key timers:
- `election_timeout`: random 150-300ms (Raft paper recommendation)
- `heartbeat_interval`: typically election_timeout / 10

## Common Test Pitfalls

### test_exponential_backoff_on_retries failing

RecoveryActionExecutor starts background threads in `__init__` that call `time.sleep`.
`@patch("time.sleep")` patches globally, so sleep count includes init-time calls.

**Fix**: call `mock_sleep.reset_mock()` AFTER creating the executor, BEFORE calling `execute()`.

### Snapshot test finding wrong extension

```python
# WRONG (old):
snapshot_file = node.storage.snapshot_dir / "snapshot_0000000003.pkl"

# CORRECT (current):
snapshot_file = node.storage.snapshot_dir / "snapshot_0000000003.json"
# or for compressed:
snapshot_file = node.storage.snapshot_dir / "snapshot_0000000002.json.gz"
```

### Flaky tests in full regression

Consensus tests that pass in isolation but fail in full regression → test ordering issue.
Run with randomized order disabled to isolate:
```bash
python3 -m pytest tests/unit/consensus/ --no-cov -v -p no:randomly
```

## Raft Invariants

1. **Election safety**: At most one leader per term
2. **Log matching**: If two logs have same index+term, all previous entries are identical
3. **Leader completeness**: If entry committed in term T, present in all leaders with term > T
4. **State machine safety**: If server applied entry at index I, no other server applies different command at I

## Paxos Phases

```
Phase 1a (Prepare): Proposer → Acceptors: {prepare, n}
Phase 1b (Promise): Acceptors → Proposer: {promise, n, accepted_n, accepted_v}
Phase 2a (Accept):  Proposer → Acceptors: {accept, n, v}
Phase 2b (Accepted):Acceptors → Learners:  {accepted, n, v}
```

## PBFT Phases

```
Pre-prepare: Primary → Replicas: <PRE-PREPARE, v, n, d>
Prepare:     Replicas → All:     <PREPARE, v, n, d, i>
Commit:      Replicas → All:     <COMMIT, v, n, D(m), i>
Reply:       Replicas → Client:  <REPLY, v, t, c, i, r>
```

Toleration: `f` faulty nodes with `3f+1` total nodes.
In x0tta6bl4: `faulty_limit = (total_nodes - 1) // 3`

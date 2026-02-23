---
name: consensus-debug
description: "Diagnoses and fixes Raft, Paxos, and PBFT consensus issues in x0tta6bl4. Inspects logs, detects split-brain, partition, leader election failures, snapshot corruption. Use when user asks to: debug consensus, fix Raft, Raft split-brain, Paxos failure, PBFT issue, consensus partition, leader election stuck, snapshot error, отладь консенсус, Raft проблема, split-brain, проблема с лидером, снапшот."
---

# Consensus Debug

Diagnostic workflow for Raft (`src/consensus/`), Paxos (`src/swarm/paxos.py`), and
PBFT (`src/swarm/pbft.py`) consensus implementations in x0tta6bl4.

## Step 1: Run Consensus Tests

```bash
# Raft tests
python3 -m pytest tests/unit/consensus/ --no-cov -v

# Paxos + PBFT (swarm bundle)
python3 -m pytest tests/unit/swarm/test_lora_fl_integration_yggdrasil_optimizer_consensus_integration_paxos_pbft_unit.py --no-cov -v
```

## Step 2: Identify Failure Type

**Leader election stuck:**
```python
# Check election timeout — default is 150-300ms (random)
node.election_timeout  # should be 0.15-0.30
node.state             # should be LEADER, FOLLOWER, or CANDIDATE
node.current_term      # monotonically increasing
```

**Split-brain:**
Two nodes both claim `state == LEADER` for same term. Impossible in correct Raft, indicates:
- Clock drift causing simultaneous elections
- Network partition where both sides elected leaders for different terms
- Check `node.current_term` on all nodes — should be the same after partition heals

**Log divergence:**
```python
node.log[-1]          # last log entry
node.commit_index     # highest committed entry
node.last_applied     # highest applied entry
# Invariant: last_applied <= commit_index <= len(log) - 1
```

**Snapshot issues:**
See `references/raft-troubleshooting.md`. Key: snapshots use `.json` format (NOT `.pkl`).
```bash
ls <snapshot_dir>/
# Correct: snapshot_0000000003.json  OR  snapshot_0000000003.json.gz
# Wrong:   snapshot_0000000003.pkl   ← old format, causes ImportError
```

## Step 3: Diagnose by Error

**`FileNotFoundError: snapshot_NNNNNNNNN.pkl`**
Source migrated from pickle to JSON (RCE safety). Tests or code still using old extension.
Fix: update any `.pkl` references to `.json`.

**`RuntimeError: no leader`**
- Quorum lost (< (N/2)+1 nodes alive)
- Election timeout too short for network latency
- Fix: check `node.peers` list, ensure majority reachable

**`AssertionError: commit_index < last_applied`**
State machine applied entries ahead of consensus. Indicates snapshot restore bug.

**PBFT `prepare` messages not received:**
```python
# Check node IDs match across replicas
pbft_node.node_id       # must be unique
pbft_node.total_nodes   # must match cluster size
pbft_node.faulty_limit  # must be < total_nodes / 3
```

## Step 4: Fix Common Issues

### Raft Log Compaction
```python
# Force snapshot creation
await node.create_snapshot(index=node.commit_index)
# Verify snapshot
snap = node.storage.load_snapshot()
assert snap is not None
```

### Paxos Prepare Timeout
```python
# Increase timeout for high-latency networks
paxos_node = PaxosNode(prepare_timeout=5.0, accept_timeout=5.0)
```

### PBFT View Change
```python
# Trigger manual view change
await pbft_node.initiate_view_change()
# Wait for new primary
await asyncio.sleep(pbft_node.view_change_timeout)
```

## Step 5: Run Targeted Diagnosis

```bash
# Raft-specific (includes snapshot tests)
python3 -m pytest tests/unit/consensus/test_raft_snapshots.py --no-cov -v

# Check for test ordering pollution (flaky tests)
python3 -m pytest tests/unit/consensus/ --no-cov -v -p no:randomly
```

## References

- `references/raft-troubleshooting.md` — detailed Raft failure scenarios

# Decentralized RAG Horizon-2 RFC

Date: 2026-03-06  
Owner: `lead-coordinator`  
Status: `proposed / blocked until v1.1 live-validation gaps close`

## Decision

Do not start a broad decentralized RAG implementation during the current v1.1
release-hardening tranche.

Do capture a repo-grounded RFC now, so the knowledge-plane can start from
existing retrieval code instead of a greenfield design later.

## Why This Is Deferred

Current higher-priority live gaps remain open:

- live XDP attach and enforcement
- measured PPS benchmark with artifact
- keyless cosign/Rekor path
- live Open5GS session against a real core
- live SX1303 HAL binding

Those items still dominate the release gate for a defensible sign-off. A mesh
knowledge plane is valuable, but it is not the next unblocker for v1.1.

## Existing Repo Anchors

This RFC is intentionally based on components already present in the repository:

- `src/rag/batch_retrieval.py`
  Current parallel retrieval path (`BatchRetriever`) with batch query/result
  types, throughput/latency stats, and worker-based execution.
- `src/ledger/rag_search.py`
  Existing semantic search integration over `CONTINUITY.md`, already using
  `RAGPipeline`, chunking, metadata, and `VectorIndex (HNSW)`.
- `src/api/ledger_endpoints.py`
  Existing API surface for index/search/status operations.
- `plans/agent_swarm_architecture.md`
  Existing design note that already names `SwarmRAGCoordinator` as an extension
  point for the current batch retrieval layer.

This means the likely starting point is not "invent a new RAG stack", but
"evolve the current retrieval layer into a distributed knowledge plane."

## Proposed MVP Boundary

The first decentralized RAG MVP should be limited to:

1. local shard retrieval on each node
2. shard metadata routing across the mesh
3. zero-trust access checks before retrieval
4. merged top-k context assembly
5. generation only from retrieved context

It should explicitly avoid in phase 1:

- global replication of all embeddings to all nodes
- a single central vector database as a permanent design
- mixing retrieval orchestration and generation in one opaque agent
- production claims about recall/latency/privacy before dedicated evidence exists

## Proposed Architecture Shape

### Data plane

- Local sparse retrieval per node for cheap lexical recall.
- Local dense retrieval per capable node using the same family already implied by
  `VectorIndex (HNSW)` in `src/ledger/rag_search.py`.
- Compact retrieval profile for weaker edge nodes later, only after the routing
  and ACL model are stable.

### Control plane

- Lightweight shard catalog:
  - shard id
  - topic/domain
  - owner node
  - tenant / ACL tag
  - freshness / stale age
  - node health
- Mesh-aware broker that decides:
  - local-only retrieval
  - remote fan-out
  - degraded fallback when neighbors are unavailable

### Security plane

- Zero-trust retrieval request identity
- shard-level ACL/policy checks before retrieval
- response assembly from only authorized chunks

## Minimum Deliverables When This Starts

1. `SwarmRAGCoordinator` design and interface contract
2. shard metadata schema
3. retrieval policy / ACL schema
4. node-local index profile (`sparse + dense`)
5. query-routing and merge strategy
6. observability contract:
   - retrieval latency
   - local hit ratio
   - remote fan-out count
   - policy denials
   - stale shard age

## Start Criteria

This track may move from `blocked` to `ready` only when all of the following are
true:

1. v1.1 live-validation blockers have an updated release-gate snapshot
2. live Open5GS and eBPF status are no longer drifting across docs
3. current roadmap queue is stable for the existing agent lanes
4. one owner is assigned for architecture and one for zero-trust retrieval policy

## Proposed Agent Split For Future Work

- architecture owner: retrieval topology, shard model, query broker contract
- security owner: zero-trust identity, ACLs, tenant isolation for retrieval
- implementation owner later: mesh transport and shard sync mechanics

## Exit Condition For This RFC

This RFC is complete when:

- the roadmap queue contains a blocked Horizon-2 item for decentralized RAG
- the starting assumptions are documented in one place
- no current release docs are polluted with premature RAG execution claims

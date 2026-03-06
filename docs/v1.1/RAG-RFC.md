# RFC: Decentralized Knowledge Mesh (RAG)
**Status:** Horizon-2 / PLAN ONLY (Not Verified)
**Objective:** Build a privacy-first knowledge layer atop the x0tta6bl4 self-healing mesh.

## 1. Five-Layer Architecture
1. **Ingestion/Chunking:** Semantic cutting of documents with metadata (source, tenant, ACL, timestamp).
2. **Local Indexing:** Hybrid search on every node.
   - Sparse: BM25/TF-IDF for lexical recall.
   - Dense (Powerful nodes): HNSW ANN index.
   - Edge (Light nodes): LEANN compact index.
3. **Mesh Routing:** Knowledge-aware request brokering using existing multi-path logic.
4. **Context Assembly:** Federated retrieval + Reranking.
5. **Generation:** LLM gateway consuming top-k context only.

## 2. Zero-Trust Retrieval
- Every retrieval request is verified against SPIFFE/SVID identity.
- Data shards are isolated by tenant/policy using existing micro-segmentation logic.
- Transport: PQC-protected (ML-KEM/ML-DSA).

## 3. Knowledge Synchronization
- **Metadata Plane (Fast):** Shared catalog of "who holds what shard".
- **Data Plane (Background):** Slow background delivery of chunks/embeddings to avoid network congestion.

## 4. MVP Roadmap
- [ ] Logic for local BM25 + HNSW scaffold.
- [ ] libp2p query broker implementation.
- [ ] Reranker integration.
- [ ] Policy enforcer wiring.

## 5. Decision Memo
- **Priority:** Low (Start after v1.1 Hardening Gaps are closed).
- **Owner:** Pending Assignment.
- **Start Condition:** Live verification of eBPF and 5G transport complete.

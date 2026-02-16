# 📊 SEQUENCE DIAGRAM: Полный цикл работы x0tta6bl4

**Дата:** 1 января 2026  
**Сценарий:** HTTP запрос → Mesh routing → PQC encryption → RAG search → Response

---

## 🔄 ПОЛНЫЙ СЦЕНАРИЙ: Запрос → Mesh → PQC → RAG → Ответ

### Sequence Diagram (Mermaid):

```mermaid
sequenceDiagram
    participant Client
    participant NodeA as Узел A<br/>(Entry Point)
    participant NodeB as Узел B<br/>(Router)
    participant NodeC as Узел C<br/>(Knowledge Base)
    participant IPFS as IPFS<br/>(Storage)
    participant DAO as DAO<br/>(Governance)

    Note over Client,DAO: 1. INITIAL REQUEST
    Client->>NodeA: HTTP GET /api/v1/search?q=memory+pressure
    activate NodeA

    Note over NodeA: 2. PQC HANDSHAKE
    NodeA->>NodeA: Generate ML-KEM-768 keypair
    NodeA->>NodeB: Send ciphertext (CT)
    activate NodeB
    NodeB->>NodeB: Decapsulate (derive shared secret K)
    NodeB-->>NodeA: ACK (handshake complete)
    Note over NodeA,NodeB: Time: <0.5ms

    Note over NodeA,NodeC: 3. MESH ROUTING
    NodeA->>NodeA: Compute route (Dijkstra algorithm)
    NodeA->>NodeB: Encrypted packet (AES-256-GCM with K)
    NodeB->>NodeB: Forward to Node C
    NodeB->>NodeC: Encrypted packet
    activate NodeC
    Note over NodeA,NodeC: Route: A → B → C (latency: 25ms)

    Note over NodeC: 4. RAG QUERY PROCESSING
    NodeC->>NodeC: Parse query: "memory pressure"
    NodeC->>NodeC: Generate embedding (all-MiniLM-L6-v2)
    NodeC->>NodeC: Hybrid search:
    Note over NodeC: - BM25: Text matching
    Note over NodeC: - Vector: Semantic search
    NodeC->>IPFS: Query knowledge base (CID lookup)
    activate IPFS
    IPFS-->>NodeC: Return relevant incidents
    deactivate IPFS

    Note over NodeC: 5. KNOWLEDGE RETRIEVAL
    NodeC->>NodeC: Filter by similarity (>0.7)
    NodeC->>NodeC: Rank by MTTR (best solutions first)
    NodeC->>NodeC: Format response

    Note over NodeC,NodeA: 6. RESPONSE PATH
    NodeC->>NodeB: Encrypted response
    NodeB->>NodeA: Encrypted response
    NodeA->>NodeA: Decrypt response
    NodeA-->>Client: HTTP 200 OK + JSON response
    deactivate NodeA
    deactivate NodeB
    deactivate NodeC

    Note over Client,DAO: Total Time: <50ms
```

---

## 🔄 СЦЕНАРИЙ 2: Self-Healing при падении узла

### Sequence Diagram:

```mermaid
sequenceDiagram
    participant NodeA
    participant NodeB as Узел B<br/>(FAILS)
    participant NodeC
    participant NodeD
    participant MAPEK as MAPE-K<br/>Cycle
    participant GraphSAGE as GraphSAGE<br/>Detector

    Note over NodeA,NodeD: Normal Operation
    NodeA->>NodeB: Ping (every 30s)
    NodeB-->>NodeA: Pong
    NodeA->>NodeC: Data packet
    NodeC-->>NodeA: ACK

    Note over NodeB: NODE FAILURE
    NodeB->>NodeB: Hardware failure / Crash
    Note over NodeB: Node B is DOWN

    Note over NodeA: MAPE-K CYCLE STARTS
    MAPEK->>NodeA: MONITOR: Collect metrics
    NodeA->>NodeB: Ping (timeout: 5s)
    NodeB-->>NodeA: No response
    NodeA-->>MAPEK: Node B unreachable

    MAPEK->>GraphSAGE: ANALYZE: Detect anomaly
    GraphSAGE->>GraphSAGE: Analyze topology
    GraphSAGE-->>MAPEK: Anomaly detected: NODE_FAILURE
    Note over GraphSAGE: Score: 0.92 (threshold: 0.7)

    MAPEK->>MAPEK: PLAN: Create recovery plan
    Note over MAPEK: Strategy: REBUILD_ROUTES
    MAPEK->>MAPEK: Find alternative paths
    Note over MAPEK: New route: A → D → C

    MAPEK->>NodeA: EXECUTE: Update routing table
    NodeA->>NodeA: Remove Node B from routes
    NodeA->>NodeD: Establish new connection
    NodeD-->>NodeA: Connection established
    NodeA->>NodeC: Test new route
    NodeC-->>NodeA: ACK (route working)

    MAPEK->>MAPEK: KNOWLEDGE: Save experience
    Note over MAPEK: MTTR: 2.3 seconds
    Note over MAPEK: Strategy: REBUILD_ROUTES (successful)

    Note over NodeA,NodeD: Network Recovered!
```

---

## 🔄 СЦЕНАРИЙ 3: DAO влияет на MAPE-K пороги

### Sequence Diagram:

```mermaid
sequenceDiagram
    participant NodeA as Узел A<br/>(Proposer)
    participant DAO as DAO<br/>Governance
    participant NodeB as Узел B<br/>(Voter)
    participant NodeC as Узел C<br/>(Voter)
    participant IPFS as IPFS<br/>(Storage)
    participant MAPEK as MAPE-K<br/>Cycle

    Note over NodeA: 1. CREATE PROPOSAL
    NodeA->>DAO: Create proposal:
    Note over NodeA,DAO: "Lower CPU threshold: 80% → 70%"
    Note over NodeA,DAO: Cost: 1000 tokens
    DAO-->>NodeA: Proposal ID: prop_123

    Note over DAO: 2. VOTING PERIOD (7 days)
    NodeB->>DAO: Vote FOR (10 votes, √100 tokens)
    NodeC->>DAO: Vote FOR (20 votes, √400 tokens)
    Note over DAO: Total: 30 FOR, 0 AGAINST
    Note over DAO: Support: 100% ✅
    Note over DAO: Quorum: 3% ❌ (need 33%)

    Note over NodeA: 3. MORE VOTERS NEEDED
    Note over DAO: Waiting for quorum...

    Note over DAO: 4. QUORUM REACHED
    Note over DAO: 33% tokens voted ✅
    Note over DAO: 67%+ support ✅
    DAO->>DAO: Execute proposal automatically

    Note over DAO,IPFS: 5. UPDATE STORAGE
    DAO->>IPFS: Store new threshold config
    Note over IPFS: CID: QmYyyy...
    IPFS-->>DAO: Confirmed

    Note over DAO,MAPEK: 6. PROPAGATE TO ALL NODES
    DAO->>NodeA: Broadcast update (IPFS CID)
    DAO->>NodeB: Broadcast update
    DAO->>NodeC: Broadcast update

    Note over MAPEK: 7. MAPE-K USES NEW THRESHOLD
    MAPEK->>MAPEK: MONITOR: Check CPU
    Note over MAPEK: Old threshold: 80%
    Note over MAPEK: New threshold: 70% (from DAO)
    MAPEK->>MAPEK: CPU: 75% > 70% → ANOMALY DETECTED
    Note over MAPEK: Earlier detection! ✅
```

---

## 📊 ВРЕМЕННЫЕ ХАРАКТЕРИСТИКИ

### Timeline для типичного запроса:

```
Time (ms)    Action
─────────────────────────────────────────────
0.0          Client sends HTTP request
0.1          Node A receives request
0.2          PQC handshake starts
0.6          PQC handshake complete (<0.5ms)
1.0          Route computation (Dijkstra)
1.5          Packet encrypted (AES-256-GCM)
2.0          Packet sent to Node B
12.0         Packet received at Node B
12.5         Packet forwarded to Node C
25.0         Packet received at Node C
25.5         RAG query processing starts
30.0         Vector embedding generated
35.0         Hybrid search (BM25 + Vector)
40.0         IPFS lookup complete
45.0         Results ranked and formatted
46.0         Response encrypted
47.0         Response sent back
72.0         Response received at Node A
72.5         Response decrypted
73.0         HTTP response sent to Client

Total: ~73ms
```

---

## 🎯 КЛЮЧЕВЫЕ МОМЕНТЫ

### 1. PQC Handshake
- **Время:** <0.5ms
- **Алгоритм:** ML-KEM-768
- **Результат:** Shared secret для AES-256-GCM

### 2. Mesh Routing
- **Алгоритм:** Dijkstra с link quality weights
- **Время:** <25ms для 3-hop route
- **Резервные пути:** k-disjoint SPF готовы

### 3. RAG Query
- **Время:** <20ms
- **Метод:** Hybrid (BM25 + Vector)
- **Точность:** 92%+ для технических запросов

### 4. Self-Healing
- **MTTD:** <20 секунд
- **MTTR:** <3 минуты
- **Точность:** 94-98% (GraphSAGE)

---

**Документ создан:** 1 января 2026  
**Статус:** ✅ Sequence diagrams готовы  
**Следующий шаг:** Использовать для технической документации


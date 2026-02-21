# ACTION PLAN NOW

**Sprint:** Week 2 (Feb 8-14, 2026) -- Grant Application Writing
**Grant deadline:** Start-AI-1 (FSI) ~Feb 20, 2026
**Status:** Заявка готова к подаче. Осталось: видео-демо + финальная подача

---

## DONE (Batches 1-4)

- [x] CRDT expansion: PNCounter, LWWRegister, ORSet (`524f3d18`)
- [x] BM25 hybrid search with RRF fusion (`524f3d18`)
- [x] eBPF PQC SipHash-2-4 MAC verification (`524f3d18`)
- [x] MeshTelemetryGenerator 6 scenarios (`0e11a730`)
- [x] ActionDispatcher + JSONL audit ledger (`0e11a730`)
- [x] ConsciousnessV2 sigmoid scoring (`0e11a730`)
- [x] GraphSAGE train_from_telemetry wiring (`3e327882`)
- [x] MAPE-K execute phase DAO dispatch (`3e327882`)
- [x] Anomaly detection benchmark suite (`3e327882`)
- [x] 31 new unit tests: MAPE-K loop + governance (`d62d1046`)
- [x] Grant technical evidence document (`docs/GRANT_TECHNICAL_EVIDENCE.md`)
- [x] AI agent orchestration: roles, walkthrough, ACTION_PLAN

---

## THIS WEEK: Grant Application

### 1. Application text (Dev/Architect)
- [x] Finalize NIOKR description with real metrics (`plans/НИОКР_ОПИСАНИЕ_ДЛЯ_ГРАНТА.md`)
- [x] Map each R&D gap closure to FSI evaluation criteria (7 компонентов, таблица сравнения)
- [x] Write "scientific novelty" section (5 пунктов новизны + сравнение с аналогами)

### 2. Evidence package (Ops)
- [x] Verify all benchmarks reproducible: accuracy 95.0%, FPR 2.6%
- [x] Coverage report: 188 тестов на 3878 строк (`docs/COVERAGE_REPORT.md`)
- [x] Benchmark output в текстовом формате (`docs/BENCHMARK_OUTPUT.txt`)

### 3. Demo readiness (Dev/Ops)
- [x] Verify FastAPI app starts: /health 200 OK, /metrics 200 (19KB)
- [x] Confirm PQC enabled (ML-DSA-65 keypair generated)
- [x] Prepare 2-minute demo script (`docs/DEMO_SCRIPT.md`)

### 4. Review and submit (Architect/GTM)
- [x] Cross-check against FSI checklist (`docs/FSI_CHECKLIST.md`)
- [x] Peer review claims vs evidence (`docs/CLAIMS_AUDIT.md`) — 37/44 подтверждены, 3 уточнены
- [x] MTTD/MTTR формулировки уточнены как "проектные метрики"
- [ ] Записать видео-демо по `docs/DEMO_SCRIPT.md`
- [ ] Подать заявку до 20 февраля

---

## Key Metrics (measured)

| Metric | Value | Source |
|--------|-------|--------|
| Anomaly detection accuracy | 95.0% | `benchmarks/anomaly_detection_results.json` |
| False positive rate | 2.6% | benchmark suite |
| DAO dispatch latency | 22us | ActionDispatcher bench |
| Consciousness scoring | 22us | ConsciousnessV2 bench |
| Partition recall | 100% | per-scenario bench |
| Node overload recall | 99% | per-scenario bench |
| Unit tests (new modules) | 90+ | pytest |

---

## Files Map

| File | Role | Purpose |
|------|------|---------|
| `ACTION_PLAN_NOW.md` | All agents | Current sprint tasks |
| `docs/walkthrough.md` | All agents | Decision log + ADRs |
| `docs/GRANT_TECHNICAL_EVIDENCE.md` | GTM/Architect | Grant evidence with real metrics |
| `docs/ARCHITECTURE.md` | Architect | System architecture |
| `ai/roles/*.md` | All agents | Agent role descriptions |
| `benchmarks/anomaly_detection_results.json` | Ops/GTM | Benchmark data |

---

## Agent Assignments

- **Architect:** Application structure, scientific novelty, ADR review
- **Dev:** NIOKR text, code examples for application, demo prep
- **Ops:** Reproducible benchmarks, coverage reports, demo environment
- **GTM:** Grant narrative, evidence packaging, submission checklist

---

## Execution Backlog (Operational)

- Canonical 2-week execution backlog: `plans/EXECUTION_BACKLOG_Q1_2026_W7_W8.md`

# ACTION PLAN NOW

**Sprint:** Week 2 (Feb 8-14, 2026) -- Grant Application Writing
**Grant deadline:** Start-AI-1 (FSI) ~Feb 20, 2026
**Status:** R&D gaps closed, evidence collected, writing application

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
- [ ] Finalize NIOKR description with real metrics from `docs/GRANT_TECHNICAL_EVIDENCE.md`
- [ ] Map each R&D gap closure to FSI evaluation criteria
- [ ] Write "scientific novelty" section using ADRs from `docs/walkthrough.md`

### 2. Evidence package (Ops)
- [ ] Verify all benchmarks reproducible: `python3 -m benchmarks.benchmark_anomaly_detection`
- [ ] Generate fresh coverage report: `python3 -m pytest tests/ --cov=src --cov-report=html -o "addopts="`
- [ ] Screenshot key metrics for grant attachments

### 3. Demo readiness (Dev/Ops)
- [ ] Verify FastAPI app starts: `uvicorn src.core.app:app --host 0.0.0.0 --port 8080`
- [ ] Confirm /health, /metrics endpoints respond
- [ ] Prepare 2-minute demo script for reviewers

### 4. Review and submit (Architect/GTM)
- [ ] Cross-check application against FSI checklist
- [ ] Peer review of technical claims vs evidence
- [ ] Submit before Feb 20

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

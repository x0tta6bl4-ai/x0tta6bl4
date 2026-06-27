# MAPE-K Self-Healing Loop — Autonomous Recovery

## Context

Mesh networks in hostile environments (censorship, jamming, node failure) need autonomous recovery without human intervention. MAPE-K (Monitor-Analyze-Plan-Execute over a Knowledge base) is the canonical autonomic computing loop from IBM's blueprint.

The loop runs on every mesh node. It monitors system health, analyzes anomalies, plans recovery actions, and executes them — all without central coordination.

## Architecture Decision

**Event-driven MAPE-K** with asynchronous phases connected by a thread-safe EventBus. Each phase runs in its own asyncio task. The Knowledge base is an in-memory store with optional SQLite persistence for recovery history.

## SPEC

### Module: `src/self_healing/mape_k.py`

```
class MonitorPhase:
    """Phase 1: Collect health metrics from all subsystems."""
    
    async def collect_metrics(self) -> NodeMetrics
    async def check_peers(self) -> list[PeerStatus]
    async def get_system_load(self) -> SystemLoad

class AnalyzePhase:
    """Phase 2: Detect anomalies in collected metrics."""
    
    async def analyze(self, metrics: NodeMetrics) -> list[Anomaly]
    async def correlate(self, anomalies: list[Anomaly]) -> Incident

class PlanPhase:
    """Phase 3: Generate recovery plan from detected incident."""
    
    async def plan_recovery(self, incident: Incident) -> RecoveryPlan
    async def rank_actions(self, plan: RecoveryPlan) -> RecoveryPlan

class ExecutePhase:
    """Phase 4: Execute recovery actions safely."""
    
    async def execute(self, plan: RecoveryPlan) -> ExecutionResult
    async def verify(self, result: ExecutionResult) -> bool

class KnowledgeBase:
    """Shared knowledge: history, patterns, learned responses."""
    
    async def record_incident(self, incident: Incident) -> None
    async def find_similar(self, incident: Incident) -> list[HistoricalIncident]
    async def update_effectiveness(self, action: str, success: bool) -> None
```

### Module: `src/self_healing/signed_command.py`

```
class SignedCommand:
    """Cryptographically signed recovery commands (ZTCR)."""
    
    @classmethod
    def create(cls, action: str, params: dict, signer: Signer) -> SignedCommand
    def verify(self, verifier: Verifier) -> bool
    def execute(self) -> CommandResult
```

## CONSTRAINTS

1. **NO stubs.** Every phase must have a real implementation.
2. **Asynchronous only.** All I/O-bound operations use asyncio.
3. **Thread-safe EventBus.** Phases communicate through the bus, not direct calls.
4. **Metrics are real.** Monitor must actually check CPU/memory/network — not random mock data.
5. **Recovery is verified.** ExecutePhase must verify the action succeeded, not just fire-and-forget.

## VERIFICATION

```bash
python3 -m pytest tests/unit/self_healing/test_mape_k.py -v
python3 -c "from src.self_healing.mape_k import MAPEKController; print('import OK')"
```

## METRICS

| Metric | Target | Measurement |
|--------|--------|-------------|
| MTTD (Mean Time To Detect) | < 20s | Monitor cycle time |
| MTTR (Mean Time To Recover) | ~3 min | Execute + verify cycle |
| False positives per hour | < 1 | Anomaly threshold tuning |
| Recovery success rate | > 90% | Knowledge base tracking |

## EDGE CASES

1. **All peers unreachable** — local-only recovery, no consensus required.
2. **Conflicting recovery actions** — priority-based resolution, higher severity wins.
3. **Recovery makes things worse** — rollback via SignedCommand with undo action.
4. **Knowledge base corruption** — rebuild from latest checkpoint.
5. **Loop starvation** — circuit breaker stops retry after 3 failures in 5 minutes.

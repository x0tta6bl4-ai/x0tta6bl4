# MAPE-K Architecture and Integration Guide

**Status**: ✅ PHASE 3 CORE COMPONENTS COMPLETE
**Date**: 2024-01-12
**Version**: 3.1.0

## 1. MAPE-K Overview

The MAPE-K autonomic computing loop (Monitor, Analyze, Plan, Execute, Knowledge) provides self-managing capabilities for the Westworld Charter system.

### Components

```
MONITOR (src/mape_k/monitor.py)
  ↓ Violations + Metrics
ANALYZE (src/mape_k/analyze.py)
  ↓ Analysis Results
PLAN (src/mape_k/plan.py)
  ↓ Approved Policies
EXECUTE (src/mape_k/execute.py)
  ↓ Outcomes
KNOWLEDGE (src/mape_k/knowledge.py)
  ↓ Learned Patterns
ORCHESTRATOR (src/mape_k/orchestrator.py)
  ↑ Feedback Loop
```

## 2. Monitor Component

**File**: `src/mape_k/monitor.py`
**Lines**: 280
**Status**: ✅ COMPLETE

### Purpose
Continuous monitoring of Charter system with real-time violation detection.

### Key Classes

#### PrometheusClient (Async HTTP Client)
```python
client = PrometheusClient(url="http://localhost:9090")
await client.connect()

# Instant query
result = await client.query("up{job='prometheus'}")

# Range query
result = await client.query_range(
    "rate(http_requests_total[5m])",
    start=datetime.now() - timedelta(hours=1),
    end=datetime.now()
)

await client.disconnect()
```

#### Monitor (Main Component)
```python
monitor = Monitor(
    prometheus_url="http://localhost:9090",
    interval=30  # seconds
)

# Collect violations
violations = monitor.get_violations(
    severity="critical",
    limit=50
)

# Collect metrics
metrics = monitor.get_metrics(
    metric_name_pattern="westworld_charter_*"
)

# Statistics
stats = monitor.get_violation_stats()
```

### Data Structures

#### Metric
```python
@dataclass
class Metric:
    name: str  # westworld_charter_policy_violations_total
    timestamp: datetime
    value: float
    labels: Dict[str, str]  # {"severity": "critical"}
```

#### Violation
```python
@dataclass
class Violation:
    violation_id: str
    severity: str  # critical, warning, info
    detected_at: datetime
    metric_name: str
    metric_value: float
    threshold: float
    labels: Dict[str, str]
    description: str
```

### Queries

**Critical Violations**:
```promql
increase(westworld_charter_policy_violations_total{severity="critical"}[5m]) > 0
```

**SLA Breaches**:
```promql
rate(westworld_charter_validation_latency_seconds[5m]) > 1
```

### Configuration

```python
monitor = Monitor()

# Thresholds (configurable)
monitor.thresholds = {
    'policy_violations': 10,
    'enforcement_latency': 5.0,
    'validation_latency': 2.0,
    'committee_decision': 30
}
```

## 3. Analyze Component

**File**: `src/mape_k/analyze.py`
**Lines**: 320
**Status**: ✅ COMPLETE

### Purpose
Pattern detection and root cause analysis from violations.

### Key Classes

#### PatternAnalyzer
```python
analyzer = PatternAnalyzer()

# Main entry point
analysis = analyzer.analyze(
    violations=violations,
    metrics=metrics
)
```

#### Analysis Results
```python
@dataclass
class AnalysisResult:
    patterns: List[ViolationPattern]
    root_causes: List[Tuple[str, float]]  # (cause, confidence)
    recommendations: List[str]
    confidence: float
    timestamp: datetime
```

### Pattern Detection Algorithms

#### 1. Temporal Patterns (Burst Detection)
```
Detection: 3+ violations within 60s
Confidence: 0.85
Hypothesis: "Cascade failure in progress"
```

#### 2. Spatial Patterns (Component Grouping)
```
Detection: 3+ violations same component
Confidence: 0.80
Hypothesis: "Policy misconfiguration"
```

#### 3. Causal Patterns (Correlation)
```
Detection: Validation latency correlates with enforcement failures
Confidence: 0.75
Hypothesis: "High latency blocks enforcement"
```

#### 4. Frequency Anomalies (Statistical)
```
Detection: >8 violations in 5 minutes
Confidence: 0.70
Hypothesis: "System overload or health issue"
```

### Usage Example

```python
# Analyze violations
analysis = analyzer.analyze(violations, metrics)

# Access results
print(f"Patterns: {len(analysis.patterns)}")
print(f"Root causes: {analysis.root_causes}")
print(f"Confidence: {analysis.confidence:.0%}")

# Get history
history = analyzer.get_analysis_history(limit=10)
```

## 4. Plan Component

**File**: `src/mape_k/plan.py`
**Lines**: 420
**Status**: ✅ COMPLETE

### Purpose
Generate remediation policies with cost-benefit analysis.

### Key Classes

#### ActionType (9 Remediation Actions)
```python
class ActionType(Enum):
    SCALE_UP                    # Scale workers (5→20 replicas)
    SCALE_DOWN                  # Reduce workload
    RESTART_SERVICE             # Restart service
    APPLY_POLICY                # Apply corrected policy
    BYPASS_VALIDATION           # Temporarily skip validation
    THROTTLE_REQUESTS           # Rate limiting
    ACTIVATE_EMERGENCY_OVERRIDE # Conservative mode
    REBALANCE_LOAD              # Redistribute workload
    UPDATE_CONFIGURATION        # Change settings
```

#### Priority (4 Levels)
```python
class Priority(Enum):
    CRITICAL    # Execute immediately
    HIGH        # Execute soon
    MEDIUM      # Schedule
    LOW         # Optional
```

#### Planner
```python
planner = Planner()

# Generate policies
policies = planner.generate_policies(analysis)

# Approve best policy
best = planner.get_best_policy()
planner.approve_policy(best.policy_id)

# Query policies
pending = planner.get_policies(approval_status='pending')
approved = planner.get_policies(approval_status='approved')
```

### Policy Generation Strategies

#### Validation Latency
- Action: Scale validation workers (5→20 replicas)
- Config: Batch size, timeout, parallelism
- Impact: 40-60% latency reduction
- Risk: LOW

#### Policy Misconfiguration
- Action: Apply corrected policy with rollback
- Impact: Eliminate errors
- Risk: MEDIUM

#### Cascade Prevention
- Action: Emergency override + request throttling
- Impact: Prevent cascade
- Risk: HIGH (but critical)

#### System Stabilization
- Action: Rebalance load + restart service
- Impact: 50-80% violation reduction
- Risk: MEDIUM

### Cost-Benefit Scoring

```
Cost (per action type):
- SCALE_DOWN: 0.05 (cheapest)
- SCALE_UP: 0.15
- RESTART_SERVICE: 0.20
- APPLY_POLICY: 0.30
- REBALANCE_LOAD: 0.25
- THROTTLE_REQUESTS: 0.40
- UPDATE_CONFIGURATION: 0.35
- ACTIVATE_EMERGENCY_OVERRIDE: 0.60
- BYPASS_VALIDATION: 0.70 (most expensive)

Benefit: Tied to root cause confidence (0.0-0.95)

Score = Benefit - Cost
```

### Usage Example

```python
# Generate policies
policies = planner.generate_policies(analysis)

# Get best by cost-benefit
best = planner.get_best_policy()
print(f"Best: {best.policy_id}")
print(f"  Cost: {best.cost_estimate:.2f}")
print(f"  Benefit: {best.benefit_estimate:.2f}")
print(f"  Score: {best.get_score():.2f}")

# Approve and execute
planner.approve_policy(best.policy_id)
approved = planner.get_policies(approval_status='approved')
```

## 5. Execute Component

**File**: `src/mape_k/execute.py`
**Lines**: 380
**Status**: ✅ COMPLETE

### Purpose
Apply approved remediation policies with transactional safety.

### Key Classes

#### ExecutionStatus
```python
class ExecutionStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
```

#### Executor
```python
executor = Executor(charter_url="http://localhost:8000")

# Execute policy
policy_exec = await executor.execute_policy(policy)

# Check status
print(f"Status: {policy_exec.status}")
print(f"Success: {policy_exec.success_rate:.0%}")

# Verify execution
verified = await executor.verify_execution(policy_exec)
```

### Charter Client Methods

```python
client = CharterClient()

# Scale component
await client.scale_component("validation_workers", replicas=20)

# Restart service
await client.restart_service("enforcement", graceful=True)

# Apply policy
await client.apply_policy({'policy_set': 'conservative'})

# Emergency override
await client.activate_emergency_override(duration=300)

# Rate limiting
await client.throttle_requests(rate_limit=1000)

# Load rebalancing
await client.rebalance_load(strategy='round_robin')
```

### Execution Workflow

```
1. Start policy execution
   ↓
2. Execute each action sequentially
   ├─ Action 1: Scale up (success)
   ├─ Action 2: Apply policy (success)
   ├─ Action 3: ??? (failed)
   │  └─ Trigger rollback
   ├─ Rollback Action 2
   └─ Rollback Action 1
   ↓
3. Record outcome
   ├─ Success rate: 66% (2/3)
   ├─ Status: ROLLED_BACK
   └─ Error: "Action 3 failed"
```

### Usage Example

```python
# Execute policy
policy_exec = await executor.execute_policy(best_policy)

# Check results
if policy_exec.status == ExecutionStatus.COMPLETED:
    print("✅ Policy execution successful")
else:
    print(f"❌ Execution failed: {policy_exec.error_details}")

# Get history
history = executor.get_execution_history(limit=20)
```

## 6. Knowledge Component

**File**: `src/mape_k/knowledge.py`
**Lines**: 380
**Status**: ✅ COMPLETE

### Purpose
Track policy outcomes and enable ML-based learning.

### Key Classes

#### OutcomeType
```python
class OutcomeType(Enum):
    SUCCESS = "success"              # Resolved all violations
    PARTIAL = "partial"              # Reduced violations 50%+
    INEFFECTIVE = "ineffective"      # Reduced violations <50%
    DEGRADATION = "degradation"      # Made things worse
    UNKNOWN = "unknown"              # Unknown outcome
```

#### Knowledge Base
```python
knowledge = Knowledge()

# Record outcome
outcome = await knowledge.record_outcome(
    policy_id="policy_123",
    executed_at=datetime.now(),
    violations_before=10,
    violations_after=0,
    time_to_stabilization=5.2
)

# Update patterns from outcome
await knowledge.update_patterns(policy, outcome)

# Generate learning insights
insights = await knowledge.generate_insights()
```

### Learning Process

```
1. Execute Policy
   ↓
2. Measure Outcome
   ├─ Violations before: 10
   ├─ Violations after: 2
   └─ Time: 5.2s
   ↓
3. Update Patterns
   ├─ SCALE_UP success rate: 85% (5/6 successful)
   ├─ Avg time to effect: 4.8s
   └─ Confidence: 0.83 (n=6)
   ↓
4. Generate Insights
   ├─ "SCALE_UP is 85% effective"
   ├─ "Takes ~5s to stabilize"
   └─ "Recommend for validation_latency"
```

### Usage Example

```python
# Record and learn
knowledge = Knowledge()

outcome = await knowledge.record_outcome(
    policy_id="policy_123",
    executed_at=datetime.now(),
    violations_before=10,
    violations_after=0
)

await knowledge.update_patterns(policy, outcome)

# Get insights
insights = knowledge.get_insights(limit=5)
for insight in insights:
    print(f"💡 {insight.title}")
    print(f"   Confidence: {insight.confidence:.0%}")

# Get statistics
stats = knowledge.get_statistics()
print(f"Overall success rate: {stats['overall_success_rate']:.0%}")
```

## 7. Orchestrator Component

**File**: `src/mape_k/orchestrator.py`
**Lines**: 320
**Status**: ✅ COMPLETE

### Purpose
Coordinate all MAPE-K components in continuous autonomic loop.

### MAFEKOrchestrator
```python
orchestrator = MAFEKOrchestrator(
    monitor_interval=30,      # seconds
    plan_threshold=3,         # min violations
    auto_approve=True         # execute policies
)

# Start autonomic loop
await orchestrator.start()

# Check state
state = orchestrator.get_state()
print(f"Iteration: {state.iteration}")
print(f"Running: {state.is_running}")
print(f"Violations: {state.violations_detected}")

# Stop gracefully
await orchestrator.stop()
```

### Loop Iteration

```
Iteration N:
├─ [MONITOR] Collect metrics and violations
│  └─ 5 violations detected
├─ [ANALYZE] Pattern detection and root cause analysis
│  ├─ 2 patterns detected
│  └─ Root causes: validation_latency (85%), policy_bug (60%)
├─ [PLAN] Generate remediation policies
│  ├─ 3 policies generated
│  └─ Best: SCALE_UP (score: 0.65)
├─ [EXECUTE] Apply best policy
│  ├─ Status: COMPLETED
│  └─ Success rate: 100%
├─ [KNOWLEDGE] Record outcome
│  ├─ Outcome: SUCCESS
│  └─ SCALE_UP confidence: 90%
└─ Wait 30s for next iteration
```

### Statistics

```python
stats = orchestrator.get_statistics()
# {
#   'iteration': 42,
#   'uptime_seconds': 1260,
#   'violations_detected': 5,
#   'policies_generated': 3,
#   'policies_executed': 3,
#   'is_running': True,
#   'knowledge_stats': {
#     'total_outcomes': 3,
#     'overall_success_rate': 0.85,
#     'patterns_learned': 5
#   }
# }
```

## 8. Integration Example

### Complete Autonomic Loop

```python
import asyncio
from src.mape_k import MAFEKOrchestrator

# Create orchestrator
orchestrator = MAFEKOrchestrator(
    monitor_interval=30,
    plan_threshold=3,
    auto_approve=True
)

# Run autonomic loop
async def main():
    await orchestrator.start()

asyncio.run(main())
```

### Custom Control Flow

```python
from src.mape_k import (
    Monitor, PatternAnalyzer, Planner,
    Executor, Knowledge
)

async def custom_flow():
    monitor = Monitor()
    analyzer = PatternAnalyzer()
    planner = Planner()
    executor = Executor()
    knowledge = Knowledge()
    
    # Get violations
    violations = monitor.get_violations()
    
    if violations:
        # Analyze
        analysis = analyzer.analyze(violations)
        
        # Plan
        policies = planner.generate_policies(analysis)
        
        if policies:
            # Manual approval
            best = planner.get_best_policy()
            if await user_approve(best):
                planner.approve_policy(best.policy_id)
                
                # Execute
                exec_result = await executor.execute_policy(best)
                
                # Learn
                outcome = await knowledge.record_outcome(
                    policy_id=best.policy_id,
                    executed_at=datetime.now(),
                    violations_before=len(violations),
                    violations_after=len(monitor.get_violations())
                )
```

## 9. Running MAPE-K

### Start Autonomic Loop

```bash
python -c "
import asyncio
from src.mape_k import MAFEKOrchestrator

orchestrator = MAFEKOrchestrator(auto_approve=True)
asyncio.run(orchestrator.start())
"
```

### Test Components

```bash
# Test Monitor
python -m src.mape_k.monitor

# Test Analyze
python -m src.mape_k.analyze

# Test Plan
python -m src.mape_k.plan

# Test Execute
python -m src.mape_k.execute

# Test Knowledge
python -m src.mape_k.knowledge

# Run orchestrator
python -m src.mape_k.orchestrator
```

## 10. Configuration

### Environment Variables

```bash
PROMETHEUS_URL=http://localhost:9090
CHARTER_URL=http://localhost:8000
ALERTMANAGER_URL=http://localhost:9093

MAPE_K_INTERVAL=30
MAPE_K_THRESHOLD=3
MAPE_K_AUTO_APPROVE=true
```

### Python Configuration

```python
from src.mape_k import MAFEKOrchestrator

orchestrator = MAFEKOrchestrator(
    monitor_interval=30,        # Collection frequency
    plan_threshold=3,           # Min violations to plan
    auto_approve=False          # Require human approval
)
```

## 11. Troubleshooting

### Prometheus Connection Fails
```
Error: Cannot connect to http://localhost:9090
Fix: Ensure Prometheus is running on port 9090
Command: docker-compose ps | grep prometheus
```

### No Violations Detected
```
Possible causes:
1. System is healthy (normal)
2. Metrics not exported yet
3. Thresholds too high

Check: monitor.get_metric_stats()
```

### Policies Not Executing
```
Causes:
1. auto_approve=False (requires manual approval)
2. violations < plan_threshold
3. Charter API unreachable

Fix: Check orchestrator.get_state().error
```

## 12. Monitoring MAPE-K

### Health Check

```python
stats = orchestrator.get_statistics()

# Check iteration frequency
iterations_per_minute = stats['iteration'] / (stats['uptime_seconds'] / 60)
print(f"Iterations/min: {iterations_per_minute:.1f}")

# Check policy effectiveness
if stats['policies_executed'] > 0:
    knowledge_stats = stats['knowledge_stats']
    success_rate = knowledge_stats['overall_success_rate']
    print(f"Policy success rate: {success_rate:.0%}")
```

### Key Metrics

- **Iteration Time**: <10s (Monitor + Analyze + Plan + Execute + Knowledge)
- **Violation Detection**: <5s (includes Prometheus query time)
- **Policy Effectiveness**: >70% (success rate)
- **Time to Stabilization**: <15s (from execution start)

---

**Next Phase**: Integration with Charter system and E2E testing

# Phase 3 Integration Guide

## Overview

Phase 3 Integration connects the MAPE-K core components with real Charter API and AlertManager infrastructure. This document provides:

1. Architecture overview
2. Component integration patterns
3. Deployment procedures
4. Testing strategies
5. Troubleshooting guide

## Integration Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Prometheus (9090)                     │
│                  Metric Collection                      │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│              AlertManager (9093)                        │
│             Alert Routing & Storage                     │
└──────────────────────┬──────────────────────────────────┘
                       │
         ┌─────────────┴─────────────┐
         ▼                           ▼
    ┌─────────────┐           ┌──────────────┐
    │   Monitor   │           │ AlertManager │
    │  Component  │           │   Client     │
    └──────┬──────┘           └──────────────┘
           │
           ▼
    ┌─────────────┐
    │   Analyze   │
    │  Component  │
    └──────┬──────┘
           │
           ▼
    ┌─────────────┐
    │    Plan     │
    │  Component  │
    └──────┬──────┘
           │
           ▼
    ┌─────────────┐          ┌──────────────┐
    │  Execute    │◄────────►│   Charter    │
    │  Component  │          │   Client     │
    └──────┬──────┘          └──────────────┘
           │
           ▼
    ┌─────────────┐
    │  Knowledge  │
    │  Component  │
    └─────────────┘
           ▲
           │ (Feedback loop)
           └─────────────────────────────────────┘
```

## Component Integrations

### 1. Monitor ↔ AlertManager

**Purpose**: Real-time violation detection via alert webhooks

**Integration Points**:
- Prometheus collects Charter metrics
- AlertManager triggers on configured rules
- Monitor component queries Prometheus for violations
- AlertManager webhook notifies Monitor of critical issues

**Configuration**:
```yaml
monitor:
  prometheus_url: http://prometheus:9090
  poll_interval: 30  # seconds
```

### 2. Analyze ↔ Monitor

**Data Flow**: Violations → Patterns

**Integration Patterns**:
```python
# Monitor produces violations
violations = await monitor.get_violations()

# Analyze consumes violations
analysis = analyzer.analyze(violations, metrics)

# Results: patterns with confidence scores
```

**Pattern Detection Algorithms**:
- Temporal: Burst detection (60s window)
- Spatial: Component grouping (3+ same component)
- Causal: Correlation analysis
- Frequency: Anomaly detection

### 3. Plan ↔ Analyze

**Data Flow**: Analysis → Policies

**Integration Pattern**:
```python
# Analysis result with patterns
analysis = analyzer.analyze(violations, metrics)

# Planner generates policies
policies = planner.generate_policies(analysis)

# Results: ranked policies with cost-benefit scoring
```

**Cost-Benefit Model**:
- Benefit: 0.0-0.95 (from analysis confidence)
- Cost: 0.05-0.70 (per action type)
- Score: benefit - cost
- Execution: highest score first

### 4. Execute ↔ Charter API

**Purpose**: Policy application via Charter consensus system

**Integration Methods**:
```python
# Real Charter Client
charter = RealCharterClient(
    base_url="http://charter:8000",
    api_key="staging-key"
)

# Connect and execute policy
await charter.connect()
await charter.apply_policy(policy_config)
await charter.disconnect()
```

**Charter API Endpoints**:
- `GET /api/v1/policies` - List active policies
- `POST /api/v1/policies/apply` - Apply new policy
- `POST /api/v1/policies/validate` - Pre-flight validation
- `POST /api/v1/policies/{id}/rollback` - Rollback policy
- `GET /api/v1/committee/state` - Committee status
- `POST /api/v1/committee/scale` - Adjust committee size
- `POST /api/v1/committee/restart` - Restart committee

### 5. Knowledge ↔ Execute

**Purpose**: Learning from policy outcomes

**Integration Pattern**:
```python
# Execute produces outcomes
outcome = PolicyOutcome(
    policy_id=execution.policy_id,
    action_type=action.type,
    outcome_type=determine_outcome(before, after),
    metric_before=before_value,
    metric_after=after_value
)

# Knowledge records and learns
knowledge.record_outcome(outcome)
patterns = knowledge.update_patterns()
insights = knowledge.generate_insights()
```

**Outcome Types**:
- SUCCESS: Violation resolved
- PARTIAL: Partially resolved
- INEFFECTIVE: No improvement
- DEGRADATION: Made worse
- UNKNOWN: Cannot determine

### 6. Orchestrator ↔ All Components

**Purpose**: Coordinate full MAPE-K loop

**Loop Sequence** (30s interval):
```python
# Continuous operation
while running:
    # 1. Monitor: Collect metrics
    violations = monitor.get_violations()
    
    # 2. Analyze: Detect patterns
    analysis = analyzer.analyze(violations, metrics)
    
    # 3. Plan: Generate policies
    policies = planner.generate_policies(analysis)
    
    # 4. Execute: Apply best policy
    if policies:
        execution = executor.execute_policy(policies[0])
    
    # 5. Knowledge: Learn from outcome
    if execution.completed:
        knowledge.record_outcome(execution)
    
    # Sleep until next cycle
    await asyncio.sleep(30)
```

## Deployment Procedures

### Local Development

1. **Setup Python Environment**:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
pip install -e ".[ml,dev,monitoring]"
```

2. **Run Individual Components**:
```bash
# Terminal 1: Monitor component
python -m src.mape_k.monitor

# Terminal 2: Orchestrator
python -m src.mape_k.orchestrator

# Terminal 3: API
python -m src.core.app --reload
```

3. **Run Tests**:
```bash
pytest tests/test_mape_k.py -v
pytest tests/test_phase3_integration.py -v
```

### Docker Staging Environment

1. **Build Images**:
```bash
docker-compose -f docker-compose.staging.yml build
```

2. **Start Services**:
```bash
docker-compose -f docker-compose.staging.yml up -d
```

3. **Verify Health**:
```bash
curl http://localhost:9090/-/healthy    # Prometheus
curl http://localhost:9093/-/healthy    # AlertManager
curl http://localhost:8000/health       # Charter
curl http://localhost:8001/health       # MAPE-K
```

4. **View Logs**:
```bash
docker-compose -f docker-compose.staging.yml logs -f mape-k
docker-compose -f docker-compose.staging.yml logs -f charter
```

5. **Stop Services**:
```bash
docker-compose -f docker-compose.staging.yml down
```

### Production Deployment

1. **Create Kubernetes ConfigMap**:
```bash
kubectl create configmap mape-k-config --from-file=config/mape_k_config.yaml
```

2. **Deploy to Kubernetes**:
```bash
kubectl apply -f deployment/kubernetes/mape-k-deployment.yaml
kubectl apply -f deployment/kubernetes/mape-k-service.yaml
```

3. **Verify Deployment**:
```bash
kubectl get pods -l app=mape-k
kubectl logs -f deployment/mape-k
```

## Testing Strategies

### Unit Tests

**Location**: `tests/test_mape_k.py`

```bash
# Run all component tests
pytest tests/test_mape_k.py -v

# Run specific component tests
pytest tests/test_mape_k.py::TestMonitor -v
pytest tests/test_mape_k.py::TestAnalyzer -v
pytest tests/test_mape_k.py::TestPlanner -v
```

### Integration Tests

**Location**: `tests/test_phase3_integration.py`

```bash
# Run Charter integration tests
pytest tests/test_phase3_integration.py::TestChartorIntegration -v

# Run AlertManager integration tests
pytest tests/test_phase3_integration.py::TestAlertManagerIntegration -v

# Run full MAPE-K pipeline tests
pytest tests/test_phase3_integration.py::TestFullMAPEKPipeline -v
```

### E2E Tests

```bash
# Start staging environment
docker-compose -f docker-compose.staging.yml up -d

# Run E2E tests
pytest tests/test_e2e.py -v

# Clean up
docker-compose -f docker-compose.staging.yml down
```

### Performance Tests

```bash
# Run benchmark suite
make benchmark

# Test with load generation
locust -f tests/load_tests.py --host=http://localhost:8001
```

## Troubleshooting

### Monitor Component Issues

**Problem**: No violations detected

```bash
# Check Prometheus connectivity
curl http://localhost:9090/api/v1/query?query=up

# Check PromQL query syntax
curl "http://localhost:9090/api/v1/query?query=westworld_charter_validation_latency_seconds"

# Solution: Verify Charter metrics are being scraped
```

### Analyze Component Issues

**Problem**: Patterns not detected

```python
# Debug: Check analysis result
analysis = analyzer.analyze(violations, metrics)
print(f"Patterns found: {len(analysis.patterns)}")
print(f"Confidence: {[p.confidence for p in analysis.patterns]}")

# Solution: Ensure violations meet pattern thresholds
```

### Execute Component Issues

**Problem**: Policies not applied

```bash
# Check Charter API connectivity
curl http://localhost:8000/health

# Check policy validation
curl -X POST http://localhost:8000/api/v1/policies/validate \
  -H "Content-Type: application/json" \
  -d '{"action": "scale_up", "replicas": 5}'

# Solution: Verify Charter API is running and accessible
```

### Knowledge Component Issues

**Problem**: Patterns not learning

```python
# Debug: Check knowledge base state
print(f"Outcomes recorded: {len(knowledge.policy_outcomes)}")
print(f"Patterns learned: {knowledge.policy_patterns}")

# Solution: Ensure outcomes are being recorded properly
```

### Integration Tests Failing

```bash
# Run with verbose logging
pytest tests/test_phase3_integration.py -vv -s

# Run specific test with debug info
pytest tests/test_phase3_integration.py::TestMAPEKWithCharterIntegration::test_monitor_feeds_to_analyze -vv

# Solution: Check component initialization and data types
```

## Monitoring Integration

### Metrics to Monitor

**Prometheus Queries**:
```promql
# MAPE-K Loop Performance
rate(mape_k_loop_duration_seconds[1m])
histogram_quantile(0.95, mape_k_loop_duration_seconds)

# Policy Execution Success
rate(mape_k_policy_executions_total{status="success"}[5m])
rate(mape_k_policy_executions_total{status="failed"}[5m])

# Charter API Response Time
histogram_quantile(0.99, charter_api_response_duration_seconds)

# Alert Handling
rate(mape_k_alerts_received_total[5m])
rate(mape_k_alerts_processed_total[5m])
```

### Dashboard Access

- **Grafana**: http://localhost:3000 (admin/admin)
- **Prometheus**: http://localhost:9090
- **AlertManager**: http://localhost:9093

### Alert Rules

**Critical Alerts**:
- `MAFEKLoopFailure`: Loop not executing
- `CharterAPIDown`: Charter API unreachable
- `PrometheusScrapeFailure`: Metric collection failure

## Configuration Reference

See `config/mape_k_config.yaml` for all configurable parameters.

### Key Configuration Sections

1. **Orchestrator**: Loop interval, logging level
2. **Monitor**: Prometheus URL, metric thresholds
3. **Analyze**: Pattern algorithms, sensitivity
4. **Plan**: Cost model, policy generation
5. **Execute**: Charter URL, timeout, rollback
6. **Knowledge**: Database backend, learning mode
7. **AlertManager**: Webhook configuration
8. **API**: Server configuration
9. **Logging**: Log levels, format, rotation

## Next Steps

1. ✅ Charter API Client - COMPLETE
2. ✅ AlertManager Client - COMPLETE
3. ✅ E2E Integration Tests - COMPLETE
4. ⏳ Staging Deployment - Deploy with Docker Compose
5. ⏳ Production Rollout - Kubernetes deployment
6. ⏳ Continuous Monitoring - Dashboard setup

## Additional Resources

- [MAPE-K Architecture](../phase3/MAPE_K_ARCHITECTURE.md)
- [Component Documentation](../phase3/COMPONENTS.md)
- [API Reference](../API_REFERENCE.md)
- [Deployment Guide](../DEPLOYMENT.md)
- [Operations Runbook](../OPERATIONS.md)

## Support

For issues or questions:
1. Check this integration guide
2. Review component logs
3. Run diagnostic tests
4. Consult architecture documentation
5. Open issue in repository

---

**Last Updated**: January 2026
**Version**: 3.1.0

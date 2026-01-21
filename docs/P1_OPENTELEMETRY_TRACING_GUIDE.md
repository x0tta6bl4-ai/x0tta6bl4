# P1 #3: OpenTelemetry Distributed Tracing Guide

## Overview

x0tta6bl4 now includes comprehensive distributed tracing using OpenTelemetry. This enables end-to-end visibility into:
- MAPE-K autonomic loop execution
- Mesh network operations
- SPIFFE/SPIRE identity management
- ML model inference and training
- Distributed ledger operations
- DAO governance
- eBPF program execution
- Federated learning training
- Raft consensus operations
- CRDT synchronization

## Installation

### 1. Install Dependencies

All OpenTelemetry dependencies are included in `requirements.txt`:

```bash
pip install -r requirements.txt
```

Or manually:

```bash
pip install opentelemetry-api==1.21.0 \
            opentelemetry-sdk==1.21.0 \
            opentelemetry-exporter-jaeger-thrift==1.21.0 \
            opentelemetry-exporter-prometheus==0.42b0 \
            opentelemetry-instrumentation-fastapi==0.42b0 \
            opentelemetry-instrumentation-requests==0.42b0 \
            opentelemetry-instrumentation-httpx==0.42b0 \
            opentelemetry-instrumentation-aiohttp==0.42b0
```

### 2. Start Tracing Backend

#### Option A: Jaeger (Recommended)

```bash
docker-compose -f deploy/docker-compose.jaeger.yml up -d
```

Access UI: http://localhost:16686

#### Option B: Grafana Tempo

```bash
docker-compose -f deploy/docker-compose.jaeger.yml up -d tempo
```

Connect to Grafana (port 3000) and add Tempo data source.

## Usage

### Basic Integration

The application automatically initializes tracing in `src/core/app.py`:

```python
from src.monitoring import initialize_tracing

initialize_tracing(service_name="x0tta6bl4")
```

### MAPE-K Cycle Tracing

```python
from src.monitoring import get_mapek_spans

mapek_spans = get_mapek_spans()

# Monitor phase
with mapek_spans.monitor_phase("node-1", metrics_collected=150):
    # Collect metrics
    pass

# Analyze phase
with mapek_spans.analyze_phase("node-1", anomalies=3, confidence=0.92):
    # Detect anomalies
    pass

# Plan phase
with mapek_spans.plan_phase("node-1", actions=2):
    # Create recovery actions
    pass

# Execute phase
with mapek_spans.execute_phase("node-1", actions_executed=2, success=True):
    # Execute actions
    pass

# Knowledge phase
with mapek_spans.knowledge_phase("node-1", insights=1):
    # Store insights
    pass
```

### Mesh Network Tracing

```python
from src.monitoring import get_network_spans

network_spans = get_network_spans()

with network_spans.node_discovery("node-1", discovered_nodes=5):
    # Discover peer nodes
    pass

with network_spans.route_calculation("node-1", "node-5", hops=3):
    # Calculate route
    pass

with network_spans.message_forwarding("node-1", "node-2", "msg-uuid"):
    # Forward message
    pass
```

### SPIFFE/SPIRE Tracing

```python
from src.monitoring import get_spiffe_spans

spiffe_spans = get_spiffe_spans()

with spiffe_spans.svid_fetch("node-1", ttl_seconds=3600):
    # Fetch SVID
    pass

with spiffe_spans.svid_renewal("node-1", success=True):
    # Renew SVID
    pass

with spiffe_spans.mtls_handshake("client-1", "server-1", duration_ms=45.2):
    # Perform mTLS handshake
    pass
```

### ML Operations Tracing

```python
from src.monitoring import get_ml_spans

ml_spans = get_ml_spans()

with ml_spans.model_inference("graphsage", input_size=1024, latency_ms=25.5):
    # Run inference
    pass

with ml_spans.model_training("rag_embedding", epoch=5, loss=0.15):
    # Train model
    pass
```

### Ledger Operations Tracing

```python
from src.monitoring import get_ledger_spans

ledger_spans = get_ledger_spans()

with ledger_spans.transaction_commit("tx-uuid-123", "transfer", size_bytes=256):
    # Commit transaction
    pass

with ledger_spans.block_creation(block_height=12345, tx_count=42):
    # Create block
    pass

with ledger_spans.state_sync(from_height=100, to_height=150):
    # Sync state
    pass
```

### DAO Governance Tracing

```python
from src.monitoring import get_dao_spans

dao_spans = get_dao_spans()

with dao_spans.proposal_creation("prop-123", "budget_allocation"):
    # Create proposal
    pass

with dao_spans.vote_casting("prop-123", "voter-1", "yes"):
    # Cast vote
    pass

with dao_spans.proposal_execution("prop-123", success=True):
    # Execute proposal
    pass
```

### eBPF Operations Tracing

```python
from src.monitoring import get_ebpf_spans

ebpf_spans = get_ebpf_spans()

with ebpf_spans.program_compilation("network_monitor", "5.10.0"):
    # Compile eBPF program
    pass

with ebpf_spans.program_execution("network_monitor", event_count=1000):
    # Execute eBPF program
    pass

with ebpf_spans.kprobe_trigger("tcp_connect", "tcp_v4_connect"):
    # Trigger kprobe
    pass
```

### Federated Learning Tracing

```python
from src.monitoring import get_fl_spans

fl_spans = get_fl_spans()

with fl_spans.local_training("client-1", round_num=5, epochs=3):
    # Local model training
    pass

with fl_spans.model_aggregation(round_num=5, client_count=10):
    # Aggregate models
    pass

with fl_spans.model_upload("client-1", model_size_bytes=1024*1024):
    # Upload local model
    pass
```

### Custom Spans

```python
from src.monitoring import get_tracer_manager

manager = get_tracer_manager()

# Context manager style
with manager.span("custom_operation", {"key": "value"}):
    # Custom operation
    pass

# Decorator style
@manager.span_decorator("custom_function", service="myservice")
def my_function():
    pass
```

## Configuration

### Environment Variables

```bash
# Jaeger configuration
JAEGER_AGENT_HOST=localhost
JAEGER_AGENT_PORT=6831

# Disable tracing (optional)
OTEL_ENABLED=false

# Sample rate (0.0-1.0)
OTEL_SAMPLER_ARG=1.0
```

### Advanced Configuration

Edit `infra/monitoring/jaeger-config.yml` or `infra/monitoring/tempo-config.yml`:

```yaml
sampler:
  type: probabilistic  # or: const, remote
  param: 0.1          # 10% sampling

reporter_loggers: false  # Disable verbose logging

metrics:
  backend: prometheus
```

## Querying Traces

### Jaeger UI (http://localhost:16686)

1. **Service**: Select `x0tta6bl4`
2. **Operation**: Filter by operation name (e.g., `mape_k.monitor`)
3. **Tags**: Add tags for filtering (e.g., `node_id=node-1`)
4. **Trace Duration**: Find slow operations

### Example Queries

```
# Find MAPE-K cycles
service="x0tta6bl4" AND span.kind="INTERNAL" AND name="mape_k.*"

# Find mTLS handshakes
service="x0tta6bl4" AND name="spiffe.mtls_handshake" AND duration >= 50ms

# Find failed proposals
service="x0tta6bl4" AND name="dao.proposal_execute" AND success=false

# Find slow GraphSAGE inferences
service="x0tta6bl4" AND name="ml.inference" AND latency_ms >= 100
```

## Span Attributes

### MAPE-K Spans
- `node_id`: Autonomic node identifier
- `metrics_count`: Number of metrics collected
- `anomalies_detected`: Number of anomalies
- `confidence`: Anomaly detection confidence (0-1)
- `actions_planned`: Number of recovery actions
- `actions_executed`: Number of executed actions
- `success`: Operation success boolean
- `insights_stored`: Number of insights

### Network Spans
- `source_node`: Source node ID
- `destination`: Destination node ID
- `nodes_discovered`: Count of discovered nodes
- `hops`: Number of hops in route
- `message_id`: Message identifier

### SPIFFE Spans
- `node_id`: Node identifier
- `ttl_seconds`: SVID time-to-live
- `client`: Client identifier
- `server`: Server identifier
- `duration_ms`: Operation duration

### ML Spans
- `model`: Model name
- `input_size`: Input data size
- `latency_ms`: Inference latency
- `epoch`: Training epoch number
- `loss`: Training loss value

### Ledger Spans
- `tx_id`: Transaction ID
- `tx_type`: Transaction type
- `size_bytes`: Transaction size
- `block_height`: Block height
- `tx_count`: Transactions in block

### DAO Spans
- `proposal_id`: Proposal identifier
- `proposal_type`: Type of proposal
- `voter`: Voter address
- `vote_type`: Vote direction (yes/no)
- `votes_needed`: Votes required for quorum
- `votes_received`: Votes cast

### eBPF Spans
- `program`: Program name
- `kernel`: Kernel version
- `events`: Event count
- `probe`: Probe name
- `function`: Kernel function

### FL Spans
- `client_id`: Client identifier
- `round`: FL round number
- `epochs`: Training epochs
- `clients`: Total clients
- `model_size_bytes`: Model size

## Performance Considerations

### Sampling

For high-volume operations, use sampling to reduce overhead:

```yaml
sampler:
  type: probabilistic
  param: 0.1  # Sample 10% of traces
```

### Batch Processing

Spans are exported in batches for efficiency:

```python
BatchSpanProcessor(exporter, max_queue_size=2048, max_export_batch_size=512)
```

### Storage

- **Jaeger**: In-memory by default, configure persistent storage for production
- **Tempo**: Local filesystem, configure S3/GCS for production

## Troubleshooting

### Spans Not Appearing

1. Check Jaeger/Tempo is running:
   ```bash
   curl http://localhost:16686/api/health
   ```

2. Verify connectivity:
   ```bash
   python -c "from opentelemetry import trace; print('OpenTelemetry OK')"
   ```

3. Enable debug logging:
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```

### High Latency

1. Check sampling rate (reduce if too high)
2. Increase batch processor queue size
3. Use compression for network spans

### Storage Issues

1. Clean old traces:
   ```bash
   # Jaeger
   curl -X DELETE http://localhost:14268/api/traces
   ```

2. Increase retention:
   ```yaml
   # tempo-config.yml
   retention: 168h  # 7 days
   ```

## Integration with Prometheus

OpenTelemetry metrics are automatically exported to Prometheus:

```bash
# Query from Prometheus
rate(otel_traces_received_total[5m])
rate(otel_spans_processed_total[5m])
```

Add to Grafana for visualization.

## Best Practices

1. **Meaningful Span Names**: Use format `component.operation`
2. **Rich Attributes**: Include relevant context in span attributes
3. **Error Handling**: Always capture errors in span events
4. **Sampling**: Use adaptive sampling in production
5. **Retention**: Balance data retention with storage costs
6. **Correlation**: Use trace context for request correlation
7. **Performance**: Monitor span export overhead

## Advanced Topics

### Custom Instrumentation

```python
@manager.span_decorator("custom_operation", service="myservice")
async def my_async_function():
    pass
```

### Manual Context Propagation

```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

with tracer.start_as_current_span("parent"):
    # Current span is automatically passed to child calls
    child_function()
```

### Trace ID Extraction

```python
from opentelemetry import trace

span = trace.get_current_span()
trace_id = trace.get_current_span().get_span_context().trace_id
```

## Testing

Run tracing tests:

```bash
pytest tests/integration/test_opentelemetry_tracing.py -v
```

## References

- [OpenTelemetry Python Docs](https://opentelemetry.io/docs/instrumentation/python/)
- [Jaeger Documentation](https://www.jaegertracing.io/docs/)
- [Grafana Tempo Documentation](https://grafana.com/docs/tempo/)

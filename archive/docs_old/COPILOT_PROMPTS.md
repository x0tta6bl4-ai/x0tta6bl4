# GitHub Copilot Prompt Cookbook

Best practices and prompt templates for working with GitHub Copilot on x0tta6bl4.

---

## 🎯 General Prompts

### Creating New Module

```python
# TODO: Create a new MAPE-K monitor for network latency
# Requirements:
# - Collect latency metrics every 5s
# - Detect anomalies using z-score (threshold: 3σ)
# - Trigger alerts when latency >100ms for >30s
# - Export metrics to Prometheus
# - Use async/await for non-blocking monitoring
```

### Adding Test Coverage

```python
# TODO: Add comprehensive unit tests for SecurityModule.verify_mtls()
# Test cases:
# 1. Valid mTLS certificate → returns True
# 2. Expired certificate → raises CertificateExpiredError
# 3. Untrusted CA → raises UntrustedCAError
# 4. Missing certificate → raises MissingCertificateError
# 5. Revoked certificate → raises CertificateRevokedError
# Use pytest fixtures for mock certificates
```

---

## 🔒 Security Prompts

### Implementing Zero Trust Check

```python
# TODO: Implement Zero Trust authorization check
# Follow SPIFFE/SPIRE identity verification:
# 1. Extract SVID from request headers
# 2. Verify SVID signature against SPIRE CA
# 3. Check SVID expiration (max age: 1 hour)
# 4. Validate workload identity matches expected pattern
# 5. Log all verification attempts with correlation IDs
# Raise UnauthorizedError if any check fails
```

### Adding mTLS Handshake

```python
# TODO: Implement mTLS handshake with peer verification
# Requirements:
# - Use TLS 1.3 minimum
# - Require client certificates
# - Verify certificate chain against CA bundle
# - Check certificate revocation (OCSP)
# - Enforce cipher suite: TLS_AES_256_GCM_SHA384
# - Timeout after 5 seconds
# - Log handshake metrics (duration, cipher, peer identity)
```

---

## 🌐 Networking Prompts

### Batman-adv Integration

```python
# TODO: Create batman-adv mesh interface manager
# Features:
# - Auto-discover mesh neighbors via batman-adv protocol
# - Monitor link quality (TQ values)
# - Handle mesh topology changes (node join/leave)
# - Expose metrics: neighbor_count, avg_link_quality, mesh_uptime
# - Integrate with MAPE-K autonomic loop
# Use asyncio for non-blocking neighbor discovery
```

### eBPF Traffic Monitor

```python
# TODO: Implement eBPF-based network traffic monitor
# Requirements:
# - Attach XDP program to network interface
# - Track packets: count, bytes, protocols (TCP/UDP/ICMP)
# - Filter malicious traffic patterns (port scans, DDoS)
# - Export statistics to Prometheus every 10s
# - Use BCC or bpftrace for eBPF program loading
# Handle kernel compatibility (≥5.10)
```

---

## 🤖 ML Prompts

### RAG Pipeline

```python
# TODO: Implement RAG (Retrieval-Augmented Generation) pipeline
# Components:
# 1. Document ingestion (PDF, Markdown, plain text)
# 2. Chunking strategy (512 tokens, 20% overlap)
# 3. Embedding generation (sentence-transformers/all-MiniLM-L6-v2)
# 4. Vector storage (HNSW index, M=16, efConstruction=200)
# 5. Semantic search (top-k=5, similarity threshold: 0.7)
# 6. LLM generation (use local model or OpenAI API)
# 7. Context formatting for prompt
# Use async for I/O operations
```

### LoRA Fine-Tuning

```python
# TODO: Implement LoRA adapter training for network anomaly detection
# Architecture:
# - Base model: BERT (distilbert-base-uncased)
# - LoRA rank: r=8, alpha=32
# - Target modules: query, value projection layers
# - Training: AdamW optimizer, lr=3e-4, warmup=100 steps
# - Dataset: Network logs with anomaly labels
# - Metrics: F1 score, precision, recall
# - Save adapter weights only (not full model)
# Use HuggingFace PEFT library
```

---

## 📊 Observability Prompts

### Prometheus Metrics

```python
# TODO: Add Prometheus metrics for MAPE-K control loop
# Metrics:
# - mape_k_cycle_duration_seconds (histogram)
# - mape_k_anomalies_detected_total (counter)
# - mape_k_adaptations_applied_total (counter)
# - mape_k_failures_total (counter, labeled by stage)
# Labels: stage (monitor|analyze|plan|execute), severity
# Export on port 9090, /metrics endpoint
```

### OpenTelemetry Tracing

```python
# TODO: Add distributed tracing with OpenTelemetry
# Span structure:
# - Parent: mesh_request (contains entire request lifecycle)
#   - Child: mtls_handshake
#   - Child: batman_adv_routing
#   - Child: service_execution
#   - Child: response_serialization
# Attributes: peer_identity, request_id, latency_ms
# Export to Jaeger or Zipkin
# Sampling: 10% of requests in production
```

---

## 🧪 Testing Prompts

### Integration Test

```python
# TODO: Write integration test for mesh network formation
# Scenario:
# 1. Start 3 nodes (A, B, C) in Docker containers
# 2. Wait for batman-adv mesh convergence (max 30s)
# 3. Send test packet from A → C (should route via B)
# 4. Verify packet delivery with <50ms latency
# 5. Simulate node B failure (stop container)
# 6. Wait for mesh re-convergence (max 15s)
# 7. Verify A → C still works (alternative route)
# 8. Clean up containers
# Use pytest-docker and pytest-asyncio
```

### Security Fuzzing

```python
# TODO: Add fuzzing test for mTLS certificate parser
# Use Hypothesis library for property-based testing:
# - Generate random certificate data (valid + invalid)
# - Test parser handles malformed certificates gracefully
# - Should not crash or leak memory
# - Should raise specific exceptions (not generic Exception)
# Run 1000 iterations, timeout 60s per iteration
```

---

## 🚀 Performance Prompts

### Benchmark

```python
# TODO: Add performance benchmark for HNSW vector search
# Benchmark parameters:
# - Vector dimensions: 384 (sentence-transformers)
# - Dataset size: 100k, 500k, 1M vectors
# - Query batch sizes: 1, 10, 100
# - Measure: queries/second, p50/p95/p99 latency
# Compare: HNSW vs brute-force vs FAISS
# Use pytest-benchmark, save results to JSON
```

---

## 📝 Documentation Prompts

### API Documentation

```python
# TODO: Generate OpenAPI spec for REST API
# Endpoints:
# - GET /health → Health check
# - POST /mesh/join → Join mesh network
# - GET /mesh/neighbors → List active neighbors
# - POST /ml/predict → Run ML inference
# - GET /metrics → Prometheus metrics
# Use FastAPI automatic OpenAPI generation
# Add detailed descriptions and examples
```

---

## 💡 Tips for Better Prompts

1. **Be Specific:** Include exact requirements, edge cases, error handling
2. **Provide Context:** Mention related files, dependencies, architecture patterns
3. **Set Constraints:** Performance limits, timeout values, resource usage
4. **Request Standards:** Coding style, type hints, docstring format
5. **Include Examples:** Sample inputs/outputs, test cases

---

## 🔗 Quick Reference

### Import Patterns

```python
# Core
from src.core import mape_k, mesh_manager

# Security
from src.security import mtls, spiffe, zero_trust

# Network
from src.network import batman_adv, ebpf, hnsw

# ML
from src.ml import rag, lora, federated

# Monitoring
from src.monitoring import prometheus, otel, grafana
```

### Type Hints

```python
from typing import Optional, List, Dict, Tuple, Union, Callable
from dataclasses import dataclass
from pydantic import BaseModel, Field

# Use Pydantic for API models
class MeshJoinRequest(BaseModel):
    node_id: str = Field(..., description="Unique node identifier")
    public_key: str = Field(..., description="Ed25519 public key")
    capabilities: List[str] = Field(default_factory=list)
```

### Async Patterns

```python
import asyncio
from typing import AsyncIterator

async def monitor_neighbors() -> AsyncIterator[Neighbor]:
    """Stream neighbor discovery events."""
    while True:
        neighbors = await discover_neighbors()
        for neighbor in neighbors:
            yield neighbor
        await asyncio.sleep(5.0)
```

---

**Last Updated:** November 6, 2025  
**Maintainer:** x0tta6bl4 Team

# Production Benchmarks

This directory contains production benchmarks for x0tta6bl4 mesh network.

## Quick Start

### Prerequisites

```bash
# Install benchmark dependencies
pip install httpx

# Ensure service is running
docker-compose up -d
# or
uvicorn src.core.app:app --host 0.0.0.0 --port 8080
```

### Run All Benchmarks

```bash
# Run complete benchmark suite
python -m tests.performance.benchmark_metrics --url http://localhost:8080

# Run MTTR benchmarks
python -m tests.performance.benchmark_mttr --url http://localhost:8080 --iterations 5
```

## Benchmark Types

### 1. Performance Metrics (`benchmark_metrics.py`)

Measures:
- **PQC Latency**: Encryption/decryption time (ML-KEM-768 + ML-DSA-65)
- **GraphSAGE Inference**: Anomaly detection latency
- **API Latency**: Endpoint response times (p50, p95, p99)

**Usage:**
```bash
python -m tests.performance.benchmark_metrics \
    --url http://localhost:8080 \
    --output-dir benchmarks/results \
    --format both
```

**Output:**
- `benchmark_YYYYMMDD_HHMMSS.json` - JSON results
- `benchmark_YYYYMMDD_HHMMSS.csv` - CSV results

### 2. MTTR (Mean Time To Recovery) (`benchmark_mttr.py`)

Measures:
- **Node Failure Recovery**: Time to recover from node crash
- **Link Failure Recovery**: Time to recover from network partition

**Usage:**
```bash
python -m tests.performance.benchmark_mttr \
    --url http://localhost:8080 \
    --iterations 5 \
    --output-dir benchmarks/results
```

**Output:**
- `mttr_benchmark_YYYYMMDD_HHMMSS.json` - MTTR statistics

## Target Metrics

| Metric | Target | Current |
|--------|--------|---------|
| **PQC Encryption** | <2ms | TBD |
| **PQC Decryption** | <2ms | TBD |
| **GraphSAGE Inference** | <50ms | TBD |
| **API Latency (p95)** | <100ms | TBD |
| **API Latency (p99)** | <200ms | TBD |
| **MTTR (Node Failure)** | <3 minutes | TBD |
| **MTTR (Link Failure)** | <20 seconds | TBD |

## CI/CD Integration

### GitLab CI Example

```yaml
benchmark:
  stage: test
  script:
    - docker-compose up -d
    - sleep 10  # Wait for service to start
    - python -m tests.performance.benchmark_metrics --url http://localhost:8080
    - python -m tests.performance.benchmark_mttr --url http://localhost:8080 --iterations 3
  artifacts:
    paths:
      - benchmarks/results/*.json
      - benchmarks/results/*.csv
    expire_in: 30 days
```

### Thresholds (Block Merge on Degradation)

```yaml
benchmark_thresholds:
  script:
    - python scripts/check_benchmark_thresholds.py \
        --baseline benchmarks/baseline/baseline.json \
        --current benchmarks/results/latest.json \
        --threshold 0.10  # 10% degradation allowed
```

## Results Directory

Results are saved to `benchmarks/results/`:
- JSON format for programmatic access
- CSV format for spreadsheet analysis
- Timestamped filenames for historical tracking

## Baseline

Establish baseline by running benchmarks on stable version:
```bash
python -m tests.performance.benchmark_metrics --url http://localhost:8080
cp benchmarks/results/latest.json benchmarks/baseline/baseline.json
```

## Troubleshooting

### Service Not Available
```bash
# Check if service is running
curl http://localhost:8080/health

# Start service
docker-compose up -d
```

### PQC Not Available
```bash
# Verify LibOQS installation
python -c "from oqs import KeyEncapsulation; print('OK')"

# Install if missing
pip install liboqs-python==0.14.1
```

### GraphSAGE Not Available
```bash
# Verify PyTorch installation
python -c "import torch; print('OK')"

# Install if missing
pip install torch torch-geometric
```

## Next Steps

1. **Add Throughput Benchmarks**: Measure mesh network throughput
2. **Add Chaos Engineering**: Real node/link failures in docker-compose
3. **Add Kubernetes Benchmarks**: MTTR in k8s environment
4. **Add Load Testing**: k6/locust integration for sustained load


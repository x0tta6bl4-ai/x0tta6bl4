# FL Module Map

## Source Files

| Module | File | Lines | Purpose |
|--------|------|-------|---------|
| Coordinator | `src/federated_learning/__init__.py` | ~600 | Main FL orchestration |
| LoRA-FL | `src/federated_learning/lora_fl_integration.py` | ~400 | LoRA adapter FL |
| Aggregators | `src/federated_learning/aggregators.py` | ~500 | FedAvg, FedProx, Byzantine-robust |
| Privacy | `src/federated_learning/privacy.py` | ~350 | DP, secure aggregation |
| Compression | `src/federated_learning/compression.py` | ~200 | Gradient compression |
| FL AI bridge | `src/ai/federated_learning.py` | ~800 | AI-FL integration |

## Tests

| Test | File | Focus |
|------|------|-------|
| LoRA-FL | `tests/test_lora_fl_integration.py` | Full integration |
| Swarm-FL | `tests/unit/swarm/test_swarm_learning.py` | Swarm+FL joint |

## Aggregation Strategies

| Strategy | Byzantine | Speed | Notes |
|----------|-----------|-------|-------|
| `fedavg` | No | Fast | Baseline, no protection |
| `fedprox` | No | Medium | Handles heterogeneity |
| `byzantine_robust` | Yes | Slow | Krum / trimmed mean |
| `coordinate_median` | Yes | Medium | Coordinate-wise median |

## Byzantine Attack Types

| Attack | Effect | Detection |
|--------|--------|-----------|
| `label_flip` | Corrupts labels | Krum distance |
| `gradient_scale` | Amplifies gradient | Norm clipping |
| `model_replacement` | Backdoor | Cosine similarity |
| `noise_injection` | Random noise | Statistical test |

## Config Parameters

```python
FLConfig(
    num_rounds=10,           # total FL rounds
    num_clients=10,          # total clients in pool
    fraction_fit=0.5,        # % clients selected per round
    aggregation="fedavg",    # aggregation strategy
    byzantine_fraction=0.0,  # Byzantine clients fraction
    differential_privacy=False,
    dp_epsilon=1.0,          # DP privacy budget
    dp_delta=1e-5,           # DP failure probability
    compression="none",      # gradient compression
    local_epochs=5,          # local training epochs
    learning_rate=0.01,
)
```

## Common Issues

**High client variance (non-IID data):**
- Use `fedprox` with `mu=0.01-1.0`
- Reduce `fraction_fit` to improve convergence

**Byzantine clients not detected:**
- Ensure `aggregation="byzantine_robust"`
- Set `byzantine_fraction >= actual Byzantine fraction * 1.5` (safety margin)

**LoRA convergence slow:**
- Reduce `rank` (try 4-8 instead of 16-32)
- Increase `alpha` relative to rank

**OOM during aggregation:**
- Enable `compression="sparse"` or `"quantize"`
- Reduce `num_clients` per round

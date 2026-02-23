---
name: fl-experiment
description: "Runs and analyzes Federated Learning experiments for x0tta6bl4 including LoRA-FL integration, Byzantine fault tolerance testing, and aggregation strategy comparison. Use when user asks to: run FL experiment, test federated learning, Byzantine fault, LoRA-FL, federated training, aggregation strategy, запусти FL эксперимент, протестируй федеративное обучение, Byzantine-robust, LoRA федеративное, эксперимент с FL."
---

# FL Experiment

Federated Learning experiment runner for x0tta6bl4. The FL stack lives in
`src/federated_learning/` (26 files, ~7800 LOC) and `src/ai/federated_learning.py`.

## Step 1: Understand the Setup

```bash
ls src/federated_learning/
ls src/ai/
cat src/federated_learning/__init__.py | head -50
```

Key components:
- **Aggregators**: FedAvg, FedProx, Byzantine-robust (Krum, coordinate-wise median, trimmed mean)
- **LoRA-FL**: LoRA adapter integration at `src/federated_learning/lora_fl_integration.py`
- **Privacy**: Differential privacy (Gaussian mechanism), secure aggregation
- **Compression**: Gradient compression, sparse updates

## Step 2: Run Existing FL Tests

```bash
# Core FL tests
python3 -m pytest tests/test_lora_fl_integration.py --no-cov -v

# Unit tests (swarm bundle includes FL)
python3 -m pytest tests/unit/swarm/test_swarm_learning.py --no-cov -v

# LoRA-FL specific
python3 -m pytest tests/test_lora_fl_integration.py -k "lora" --no-cov -v
```

## Step 3: Configure an Experiment

```python
from src.federated_learning import FederatedLearningCoordinator, FLConfig

config = FLConfig(
    num_rounds=10,
    num_clients=5,
    fraction_fit=0.8,             # fraction of clients per round
    aggregation="fedavg",          # fedavg | fedprox | byzantine_robust
    byzantine_fraction=0.2,        # for robust aggregation
    differential_privacy=True,
    dp_epsilon=1.0,
    dp_delta=1e-5,
    compression="sparse",          # none | sparse | quantize
)

coordinator = FederatedLearningCoordinator(config)
```

## Step 4: Run Experiment

```python
# Simulated round (no real network)
results = coordinator.simulate_round(clients=[...])

# Check convergence
print(f"Round {results.round}: loss={results.global_loss:.4f}, acc={results.accuracy:.2%}")
```

## Step 5: Byzantine Fault Testing

```python
# Inject Byzantine clients
from src.federated_learning import ByzantineAttack

coordinator.inject_attack(
    attack=ByzantineAttack.LABEL_FLIP,
    fraction=0.3,  # 30% Byzantine
)
results = coordinator.simulate_round(clients=[...])
```

Run the dedicated Byzantine test:
```bash
python3 -m pytest tests/test_lora_fl_integration.py -k "byzantine" --no-cov -v
```

## Step 6: LoRA Integration

```python
from src.federated_learning.lora_fl_integration import LoRAFLAdapter

adapter = LoRAFLAdapter(
    base_model="llama-7b",
    rank=16,
    alpha=32,
    target_modules=["q_proj", "v_proj"],
)

# Federated fine-tuning
adapter.federated_fit(clients=[...], rounds=5)
```

## Analysing Results

```bash
# Check convergence plot (if matplotlib available)
python3 -c "
from src.federated_learning import FLMetrics
metrics = FLMetrics.load('fl_run_latest.json')
metrics.plot_convergence()
"
```

Key metrics to watch:
- **Global loss**: should decrease monotonically
- **Client variance**: high variance → data heterogeneity problem
- **Byzantine accuracy**: robust aggregator should maintain accuracy despite 20-30% adversaries

## References

- `references/fl-modules.md` — module map and API reference

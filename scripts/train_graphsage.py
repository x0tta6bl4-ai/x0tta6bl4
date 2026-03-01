#!/usr/bin/env python3
"""
GraphSAGE V2 Training Script.

Цель: Recall 92% → 96%, FPR ≤ 5%

Запуск:
  pip install torch torch-geometric numpy
  python scripts/train_graphsage.py
"""

import sys

sys.path.insert(0, "/mnt/AC74CC2974CBF3DC")

import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def check_dependencies():
    """Проверить зависимости."""
    missing = []

    try:
        import numpy as np

        print(f"✅ numpy: {np.__version__}")
    except ImportError:
        missing.append("numpy")

    try:
        import torch

        print(f"✅ torch: {torch.__version__}")
    except ImportError:
        missing.append("torch")

    try:
        import torch_geometric

        print(f"✅ torch_geometric: {torch_geometric.__version__}")
    except ImportError:
        missing.append("torch-geometric")

    if missing:
        print(f"\n⚠️ Missing: {', '.join(missing)}")
        print("Install with: pip install " + " ".join(missing))
        return False

    return True


def generate_synthetic_data(num_nodes=100, num_edges=300, anomaly_rate=0.1):
    """
    Генерировать синтетические данные для обучения.

    В реальности данные приходят из mesh-сети.
    """
    import numpy as np
    import torch

    # Node features: [cpu, mem, latency, loss, connections, uptime, errors, bandwidth]
    # Normal nodes
    normal_features = (
        np.random.randn(int(num_nodes * (1 - anomaly_rate)), 8) * 0.3 + 0.5
    )

    # Anomaly nodes (higher variance, different mean)
    anomaly_features = np.random.randn(int(num_nodes * anomaly_rate), 8) * 0.8 + 0.2

    # Combine
    x = np.vstack([normal_features, anomaly_features])
    x = np.clip(x, 0, 1)  # Normalize to [0, 1]

    # Labels
    y = np.zeros(num_nodes)
    y[int(num_nodes * (1 - anomaly_rate)) :] = 1  # Anomalies = 1

    # Random edges
    edge_index = np.random.randint(0, num_nodes, (2, num_edges))

    return (
        torch.tensor(x, dtype=torch.float32),
        torch.tensor(edge_index, dtype=torch.long),
        torch.tensor(y, dtype=torch.long),
    )


def train_model(epochs=100, lr=0.01):
    """Обучить GraphSAGE."""
    import torch
    import torch.nn.functional as F

    from src.ml.graphsage_anomaly_detector import GraphSAGEAnomalyDetectorV2

    print("\n🧠 Training GraphSAGE V2...")
    print(f"   Epochs: {epochs}")
    print(f"   Learning rate: {lr}")

    # Модель
    model = GraphSAGEAnomalyDetectorV2(input_dim=8, hidden_dim=64)

    optimizer = torch.optim.Adam(model.parameters(), lr=lr)

    # Данные
    x, edge_index, y = generate_synthetic_data(num_nodes=500, num_edges=1500)

    # Train/test split
    train_mask = torch.zeros(500, dtype=torch.bool)
    train_mask[:400] = True
    test_mask = ~train_mask

    best_recall = 0.0

    for epoch in range(epochs):
        model.train()
        optimizer.zero_grad()

        out = model(x, edge_index)
        loss = F.cross_entropy(out[train_mask], y[train_mask])
        loss.backward()
        optimizer.step()

        # Evaluate
        if (epoch + 1) % 20 == 0:
            model.eval()
            with torch.no_grad():
                pred = out[test_mask].argmax(dim=1)
                correct = (pred == y[test_mask]).sum().item()
                total = test_mask.sum().item()
                accuracy = correct / total

                # Recall for anomaly class
                anomaly_mask = y[test_mask] == 1
                if anomaly_mask.sum() > 0:
                    tp = ((pred == 1) & (y[test_mask] == 1)).sum().item()
                    fn = ((pred == 0) & (y[test_mask] == 1)).sum().item()
                    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
                else:
                    recall = 0

                # FPR
                normal_mask = y[test_mask] == 0
                if normal_mask.sum() > 0:
                    fp = ((pred == 1) & (y[test_mask] == 0)).sum().item()
                    tn = ((pred == 0) & (y[test_mask] == 0)).sum().item()
                    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0
                else:
                    fpr = 0

                if recall > best_recall:
                    best_recall = recall

                print(
                    f"   Epoch {epoch+1}: Loss={loss:.4f}, Acc={accuracy:.2%}, "
                    f"Recall={recall:.2%}, FPR={fpr:.2%}"
                )

    print(f"\n✅ Training complete!")
    print(f"   Best Recall: {best_recall:.2%}")
    print(f"   Target: ≥96%")

    # Save model
    model_path = f"/mnt/AC74CC2974CBF3DC/models/graphsage_v2_{datetime.now():%Y%m%d}.pt"
    try:
        import os

        os.makedirs("/mnt/AC74CC2974CBF3DC/models", exist_ok=True)
        torch.save(model.state_dict(), model_path)
        print(f"   Saved: {model_path}")
    except Exception as e:
        print(f"   ⚠️ Could not save: {e}")

    return model, best_recall


def main():
    print("=" * 50)
    print("GraphSAGE V2 Training Pipeline")
    print("=" * 50)

    if not check_dependencies():
        print("\n❌ Install dependencies first")
        return

    model, recall = train_model(epochs=100, lr=0.01)

    print("\n" + "=" * 50)
    if recall >= 0.96:
        print("🎉 TARGET ACHIEVED: Recall ≥ 96%")
    else:
        print(f"📈 Progress: {recall:.0%} / 96% target")
        print("   Increase epochs or tune hyperparameters")


if __name__ == "__main__":
    main()

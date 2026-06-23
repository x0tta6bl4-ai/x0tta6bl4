"""
Unsupervised Anomaly Detection on eBPF Features

Uses Isolation Forest and VAE for anomaly detection on eBPF-derived features.

Features:
- Automatic VAE training when enough data is collected
- Model persistence (save/load trained models)
- Validation and early stopping
- Automatic retraining on new data
- Improved normalization and edge case handling
"""

import json
import logging
import os
from collections import deque
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

try:
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler

    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logger.warning("scikit-learn not available, unsupervised detection disabled")

try:
    import torch
    import torch.nn as nn

    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    logger.warning("PyTorch not available, VAE disabled")


class IsolationForestDetector:
    """
    Isolation Forest for unsupervised anomaly detection on eBPF features.

    Features:
    - No labeled data required
    - Fast training and inference
    - Works well on high-dimensional eBPF metrics
    """

    def __init__(
        self,
        contamination: float = 0.1,  # Expected fraction of anomalies
        n_estimators: int = 100,
        random_state: int = 42,
    ):
        """
        Initialize Isolation Forest detector.

        Args:
            contamination: Expected fraction of outliers (0.0-0.5)
            n_estimators: Number of trees
            random_state: Random seed
        """
        if not SKLEARN_AVAILABLE:
            raise ImportError("scikit-learn required for IsolationForest")

        self.model = IsolationForest(
            contamination=contamination,
            n_estimators=n_estimators,
            random_state=random_state,
            n_jobs=-1,  # Use all CPUs
        )
        self.scaler = StandardScaler()
        self.is_trained = False
        self.feature_names = [
            "tcp_packets",
            "udp_packets",
            "icmp_packets",
            "syscall_latency",
            "packet_loss",
            "throughput",
            "cpu",
            "memory",
        ]

        logger.info(
            f"IsolationForest detector initialized (contamination={contamination})"
        )

    def train(self, features_list: List[Dict[str, float]]):
        """
        Train Isolation Forest on eBPF features.

        Args:
            features_list: List of feature dicts from eBPF metrics
        """
        # Convert to numpy array
        X = np.array(
            [
                [
                    f.get("tcp_packets", 0.0),
                    f.get("udp_packets", 0.0),
                    f.get("icmp_packets", 0.0),
                    f.get("syscall_latency", 0.0),
                    f.get("packet_loss", 0.0),
                    f.get("throughput", 0.0),
                    f.get("cpu", 0.0),
                    f.get("memory", 0.0),
                ]
                for f in features_list
            ]
        )

        # Scale features
        X_scaled = self.scaler.fit_transform(X)

        # Train model
        self.model.fit(X_scaled)
        self.is_trained = True

        logger.info(f"Trained IsolationForest on {len(features_list)} samples")

    def predict(self, features: Dict[str, float]) -> Tuple[bool, float]:
        """
        Predict anomaly on single feature vector.

        Returns:
            (is_anomaly, anomaly_score)
            score: -1 (anomaly) to +1 (normal), lower = more anomalous
        """
        if not self.is_trained:
            logger.warning("Model not trained, returning default")
            return False, 0.0

        # Convert to array
        X = np.array(
            [
                [
                    features.get("tcp_packets", 0.0),
                    features.get("udp_packets", 0.0),
                    features.get("icmp_packets", 0.0),
                    features.get("syscall_latency", 0.0),
                    features.get("packet_loss", 0.0),
                    features.get("throughput", 0.0),
                    features.get("cpu", 0.0),
                    features.get("memory", 0.0),
                ]
            ]
        )

        # Scale
        X_scaled = self.scaler.transform(X)

        # Predict
        prediction = self.model.predict(X_scaled)[0]  # -1 (anomaly) or +1 (normal)
        score = self.model.score_samples(X_scaled)[0]  # Anomaly score

        is_anomaly = prediction == -1
        # Convert score to 0-1 range (lower = more anomalous)
        normalized_score = 1.0 - (
            (score - self.model.score_samples(X_scaled).min())
            / (
                self.model.score_samples(X_scaled).max()
                - self.model.score_samples(X_scaled).min()
                + 1e-10
            )
        )

        return is_anomaly, normalized_score


if TORCH_AVAILABLE:

    class VAEDetector(nn.Module):
        """
        Variational Autoencoder for unsupervised anomaly detection.

        More sophisticated than Isolation Forest, can learn complex patterns.
        """

        def __init__(self, input_dim: int = 8, latent_dim: int = 4):
            super(VAEDetector, self).__init__()

            # Encoder
            self.encoder = nn.Sequential(
                nn.Linear(input_dim, 16),
                nn.ReLU(),
                nn.Linear(16, latent_dim * 2),  # Mean and logvar
            )

            # Decoder
            self.decoder = nn.Sequential(
                nn.Linear(latent_dim, 16),
                nn.ReLU(),
                nn.Linear(16, input_dim),
                nn.Sigmoid(),
            )

        def encode(self, x):
            """Encode input to latent space."""
            h = self.encoder(x)
            mu, logvar = h.chunk(2, dim=1)
            return mu, logvar

        def reparameterize(self, mu, logvar):
            """Reparameterization trick."""
            std = torch.exp(0.5 * logvar)
            eps = torch.randn_like(std)
            return mu + eps * std

        def decode(self, z):
            """Decode from latent space."""
            return self.decoder(z)

        def forward(self, x):
            """Forward pass."""
            mu, logvar = self.encode(x)
            z = self.reparameterize(mu, logvar)
            return self.decode(z), mu, logvar

        def anomaly_score(self, x):
            """
            Calculate anomaly score (reconstruction error).

            Higher reconstruction error = more anomalous.
            """
            x_recon, mu, logvar = self.forward(x)
            recon_error = torch.mean((x - x_recon) ** 2, dim=1)
            return recon_error.item()


class UnsupervisedAnomalyDetector:
    """
    Combines Isolation Forest and VAE for robust anomaly detection.

    Features:
    - Automatic VAE training when enough data is collected
    - Model persistence (save/load)
    - Validation and early stopping
    - Automatic retraining on new data
    """

    def __init__(
        self,
        use_isolation_forest: bool = True,
        use_vae: bool = True,  # VAE enabled by default, auto-trains when ready
        auto_train_vae: bool = True,  # Automatically train VAE when enough data
        min_samples_for_vae: int = 100,  # Minimum samples before training VAE
        model_save_path: Optional[str] = None,  # Path to save/load models
        vae_epochs: int = 100,  # Training epochs
        vae_batch_size: int = 32,
        vae_lr: float = 0.001,
        early_stopping_patience: int = 10,  # Early stopping patience
        validation_split: float = 0.2,  # Validation split for early stopping
    ):
        self.if_detector = (
            IsolationForestDetector()
            if use_isolation_forest and SKLEARN_AVAILABLE
            else None
        )
        self.vae_detector = VAEDetector() if use_vae and TORCH_AVAILABLE else None

        # VAE training configuration
        self.auto_train_vae = auto_train_vae
        self.min_samples_for_vae = min_samples_for_vae
        self.model_save_path = model_save_path or os.getenv(
            "VAE_MODEL_PATH", "./models/vae_detector"
        )
        self.vae_epochs = vae_epochs
        self.vae_batch_size = vae_batch_size
        self.vae_lr = vae_lr
        self.early_stopping_patience = early_stopping_patience
        self.validation_split = validation_split

        # Training state
        self.vae_is_trained = False
        self.vae_training_samples = deque(
            maxlen=10000
        )  # Store recent samples for retraining
        self.vae_best_loss = float("inf")
        self.vae_patience_counter = 0

        # Feature normalization params
        self.vae_feature_min = None
        self.vae_feature_max = None
        self.vae_feature_range = None

        # Create model directory if needed
        if self.model_save_path:
            Path(self.model_save_path).parent.mkdir(parents=True, exist_ok=True)

        # Try to load existing model
        if use_vae and TORCH_AVAILABLE:
            self._load_vae_model()

        logger.info(
            f"Unsupervised detector initialized: "
            f"IF={use_isolation_forest}, VAE={use_vae}, "
            f"auto_train={auto_train_vae}, trained={self.vae_is_trained}"
        )

    def add_training_sample(self, features: Dict[str, float]):
        """
        Add a training sample for automatic VAE training.

        Args:
            features: Feature dict from eBPF metrics
        """
        if self.vae_detector and self.auto_train_vae:
            self.vae_training_samples.append(features)

            # Check if we have enough samples for training
            if (
                len(self.vae_training_samples) >= self.min_samples_for_vae
                and not self.vae_is_trained
            ):
                logger.info(
                    f"📊 Collected {len(self.vae_training_samples)} samples, starting VAE training..."
                )
                self.train_vae(list(self.vae_training_samples))
            elif (
                len(self.vae_training_samples) >= self.min_samples_for_vae * 2
                and self.vae_is_trained
            ):
                # Retrain if we have 2x the minimum samples
                logger.info(
                    f"📊 Collected {len(self.vae_training_samples)} samples, retraining VAE..."
                )
                self.train_vae(list(self.vae_training_samples))

    def train(
        self,
        features_list: List[Dict[str, float]],
        vae_epochs: Optional[int] = None,
        vae_batch_size: Optional[int] = None,
        vae_lr: Optional[float] = None,
    ):
        """
        Train both detectors.

        Args:
            features_list: List of feature dicts from eBPF metrics
            vae_epochs: Number of training epochs for VAE (uses default if None)
            vae_batch_size: Batch size for VAE training (uses default if None)
            vae_lr: Learning rate for VAE training (uses default if None)
        """
        if self.if_detector:
            self.if_detector.train(features_list)

        # Train VAE if enabled
        if self.vae_detector and TORCH_AVAILABLE:
            self.train_vae(features_list, vae_epochs, vae_batch_size, vae_lr)

    def train_vae(
        self,
        features_list: List[Dict[str, float]],
        vae_epochs: Optional[int] = None,
        vae_batch_size: Optional[int] = None,
        vae_lr: Optional[float] = None,
    ):
        """
        Train VAE detector with improved features.

        Args:
            features_list: List of feature dicts from eBPF metrics
            vae_epochs: Number of training epochs (uses default if None)
            vae_batch_size: Batch size (uses default if None)
            vae_lr: Learning rate (uses default if None)
        """
        if not self.vae_detector or not TORCH_AVAILABLE:
            return

        epochs = vae_epochs or self.vae_epochs
        batch_size = vae_batch_size or self.vae_batch_size
        lr = vae_lr or self.vae_lr

        if len(features_list) < batch_size:
            logger.warning(
                f"⚠️ Not enough samples for VAE training ({len(features_list)} < {batch_size}), skipping"
            )
            return

        logger.info(f"🚀 Training VAE detector on {len(features_list)} samples...")

        # Convert features to array
        feature_array = np.array(
            [
                [
                    f.get("tcp_packets", 0.0),
                    f.get("udp_packets", 0.0),
                    f.get("icmp_packets", 0.0),
                    f.get("syscall_latency", 0.0),
                    f.get("packet_loss", 0.0),
                    f.get("throughput", 0.0),
                    f.get("cpu", 0.0),
                    f.get("memory", 0.0),
                ]
                for f in features_list
            ]
        )

        # Improved normalization: handle edge cases
        feature_min = feature_array.min(axis=0, keepdims=True)
        feature_max = feature_array.max(axis=0, keepdims=True)
        feature_range = feature_max - feature_min
        # Avoid division by zero and handle constant features
        feature_range = np.where(feature_range == 0, 1.0, feature_range)
        feature_normalized = (feature_array - feature_min) / feature_range

        # Store normalization params for inference
        self.vae_feature_min = feature_min
        self.vae_feature_max = feature_max
        self.vae_feature_range = feature_range

        # Convert to tensor
        X = torch.FloatTensor(feature_normalized)

        # Split into train/validation for early stopping
        val_size = int(len(X) * self.validation_split)
        if val_size > 0:
            indices = torch.randperm(len(X))
            train_indices = indices[val_size:]
            val_indices = indices[:val_size]
            X_train = X[train_indices]
            X_val = X[val_indices]
        else:
            X_train = X
            X_val = X

        # Setup optimizer
        optimizer = torch.optim.Adam(self.vae_detector.parameters(), lr=lr)

        # Training loop with early stopping
        self.vae_detector.train()
        self.vae_best_loss = float("inf")
        self.vae_patience_counter = 0

        for epoch in range(epochs):
            # Training phase
            train_loss = 0.0
            num_batches = 0

            # Shuffle training data
            train_indices_shuffled = torch.randperm(len(X_train))
            X_train_shuffled = X_train[train_indices_shuffled]

            for i in range(0, len(X_train_shuffled), batch_size):
                batch = X_train_shuffled[i : i + batch_size]

                optimizer.zero_grad()

                # Forward pass
                x_recon, mu, logvar = self.vae_detector(batch)

                # VAE loss: reconstruction + KL divergence
                recon_loss = torch.nn.functional.mse_loss(
                    x_recon, batch, reduction="sum"
                )
                kl_loss = -0.5 * torch.sum(1 + logvar - mu.pow(2) - logvar.exp())
                loss = recon_loss + kl_loss

                # Backward pass
                loss.backward()
                optimizer.step()

                train_loss += loss.item()
                num_batches += 1

            avg_train_loss = train_loss / num_batches if num_batches > 0 else 0.0

            # Validation phase
            self.vae_detector.eval()
            val_loss = 0.0
            with torch.no_grad():
                for i in range(0, len(X_val), batch_size):
                    batch = X_val[i : i + batch_size]
                    x_recon, mu, logvar = self.vae_detector(batch)
                    recon_loss = torch.nn.functional.mse_loss(
                        x_recon, batch, reduction="sum"
                    )
                    kl_loss = -0.5 * torch.sum(1 + logvar - mu.pow(2) - logvar.exp())
                    loss = recon_loss + kl_loss
                    val_loss += loss.item()

            avg_val_loss = (
                val_loss / (len(X_val) // batch_size + 1)
                if len(X_val) > 0
                else avg_train_loss
            )
            self.vae_detector.train()

            # Early stopping check
            if avg_val_loss < self.vae_best_loss:
                self.vae_best_loss = avg_val_loss
                self.vae_patience_counter = 0
                # Save best model
                self._save_vae_model()
            else:
                self.vae_patience_counter += 1
                if self.vae_patience_counter >= self.early_stopping_patience:
                    logger.info(
                        f"⏹️ Early stopping at epoch {epoch + 1}/{epochs} (patience: {self.early_stopping_patience})"
                    )
                    # Load best model
                    self._load_vae_model()
                    break

            if (epoch + 1) % 10 == 0:
                logger.debug(
                    f"VAE epoch {epoch + 1}/{epochs}, train_loss: {avg_train_loss:.4f}, val_loss: {avg_val_loss:.4f}"
                )

        self.vae_detector.eval()
        self.vae_is_trained = True
        logger.info(
            f"✅ VAE training completed after {epoch + 1} epochs (best val_loss: {self.vae_best_loss:.4f})"
        )

        # Save final model
        self._save_vae_model()

    def predict(self, features: Dict[str, float]) -> Dict[str, any]:
        """
        Predict anomaly using ensemble of detectors.

        Returns:
            Dict with predictions from all detectors
        """
        results = {}

        if self.if_detector:
            is_anomaly, score = self.if_detector.predict(features)
            results["isolation_forest"] = {"is_anomaly": is_anomaly, "score": score}

        if self.vae_detector:
            # Convert features to tensor
            feature_array = np.array(
                [
                    [
                        features.get("tcp_packets", 0.0),
                        features.get("udp_packets", 0.0),
                        features.get("icmp_packets", 0.0),
                        features.get("syscall_latency", 0.0),
                        features.get("packet_loss", 0.0),
                        features.get("throughput", 0.0),
                        features.get("cpu", 0.0),
                        features.get("memory", 0.0),
                    ]
                ]
            )

            # Normalize using stored params (if available from training)
            if hasattr(self, "vae_feature_min") and hasattr(self, "vae_feature_range"):
                feature_normalized = (
                    feature_array - self.vae_feature_min
                ) / self.vae_feature_range
            else:
                # Fallback: simple normalization
                feature_normalized = feature_array / (
                    np.abs(feature_array).max() + 1e-10
                )

            feature_tensor = torch.FloatTensor(feature_normalized)

            # Set to eval mode
            self.vae_detector.eval()
            with torch.no_grad():
                score = self.vae_detector.anomaly_score(feature_tensor)

            # Normalize score to [0, 1] range (higher = more anomalous)
            # Use threshold based on training distribution
            threshold = 0.3  # Can be tuned based on validation data
            results["vae"] = {
                "is_anomaly": score > threshold,
                "score": min(1.0, score),  # Cap at 1.0
            }

        # Ensemble decision (majority vote or weighted average)
        if len(results) > 1:
            anomaly_votes = sum(1 for r in results.values() if r["is_anomaly"])
            ensemble_anomaly = anomaly_votes >= len(results) / 2
            ensemble_score = np.mean([r["score"] for r in results.values()])
        elif results:
            r = list(results.values())[0]
            ensemble_anomaly = r["is_anomaly"]
            ensemble_score = r["score"]
        else:
            ensemble_anomaly = False
            ensemble_score = 0.0

        results["ensemble"] = {"is_anomaly": ensemble_anomaly, "score": ensemble_score}

        return results

    def _save_vae_model(self):
        """Save VAE model and normalization parameters."""
        if not self.vae_detector or not TORCH_AVAILABLE or not self.model_save_path:
            return

        try:
            # Save model state
            model_path = f"{self.model_save_path}.pth"
            torch.save(self.vae_detector.state_dict(), model_path)

            # Save normalization params
            norm_path = f"{self.model_save_path}_norm.json"
            norm_data = {
                "feature_min": (
                    self.vae_feature_min.tolist()
                    if self.vae_feature_min is not None
                    else None
                ),
                "feature_max": (
                    self.vae_feature_max.tolist()
                    if self.vae_feature_max is not None
                    else None
                ),
                "feature_range": (
                    self.vae_feature_range.tolist()
                    if self.vae_feature_range is not None
                    else None
                ),
                "is_trained": self.vae_is_trained,
            }

            with open(norm_path, "w") as f:
                json.dump(norm_data, f)

            logger.debug(f"💾 VAE model saved to {model_path}")
        except Exception as e:
            logger.warning(f"⚠️ Failed to save VAE model: {e}")

    def _load_vae_model(self):
        """Load VAE model and normalization parameters."""
        if not self.vae_detector or not TORCH_AVAILABLE or not self.model_save_path:
            return

        try:
            model_path = f"{self.model_save_path}.pth"
            norm_path = f"{self.model_save_path}_norm.json"

            # Load model state
            if os.path.exists(model_path):
                self.vae_detector.load_state_dict(torch.load(model_path))  # nosec B614
                self.vae_detector.eval()
                logger.info(f"📂 VAE model loaded from {model_path}")
            else:
                return

            # Load normalization params
            if os.path.exists(norm_path):
                with open(norm_path, "r") as f:
                    norm_data = json.load(f)

                if norm_data.get("feature_min"):
                    self.vae_feature_min = np.array(norm_data["feature_min"])
                    self.vae_feature_max = np.array(norm_data["feature_max"])
                    self.vae_feature_range = np.array(norm_data["feature_range"])
                    self.vae_is_trained = norm_data.get("is_trained", False)

                logger.info(f"📂 VAE normalization params loaded from {norm_path}")
        except Exception as e:
            logger.warning(f"⚠️ Failed to load VAE model: {e}")

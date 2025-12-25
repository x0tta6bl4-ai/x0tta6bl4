"""
Unsupervised Anomaly Detection on eBPF Features

Uses Isolation Forest and VAE for anomaly detection on eBPF-derived features.
"""

import logging
import numpy as np
from typing import Dict, List, Optional, Tuple
from collections import deque

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
        random_state: int = 42
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
            n_jobs=-1  # Use all CPUs
        )
        self.scaler = StandardScaler()
        self.is_trained = False
        self.feature_names = [
            'tcp_packets', 'udp_packets', 'icmp_packets',
            'syscall_latency', 'packet_loss', 'throughput',
            'cpu', 'memory'
        ]
        
        logger.info(f"IsolationForest detector initialized (contamination={contamination})")
    
    def train(self, features_list: List[Dict[str, float]]):
        """
        Train Isolation Forest on eBPF features.
        
        Args:
            features_list: List of feature dicts from eBPF metrics
        """
        # Convert to numpy array
        X = np.array([
            [
                f.get('tcp_packets', 0.0),
                f.get('udp_packets', 0.0),
                f.get('icmp_packets', 0.0),
                f.get('syscall_latency', 0.0),
                f.get('packet_loss', 0.0),
                f.get('throughput', 0.0),
                f.get('cpu', 0.0),
                f.get('memory', 0.0),
            ]
            for f in features_list
        ])
        
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
        X = np.array([[
            features.get('tcp_packets', 0.0),
            features.get('udp_packets', 0.0),
            features.get('icmp_packets', 0.0),
            features.get('syscall_latency', 0.0),
            features.get('packet_loss', 0.0),
            features.get('throughput', 0.0),
            features.get('cpu', 0.0),
            features.get('memory', 0.0),
        ]])
        
        # Scale
        X_scaled = self.scaler.transform(X)
        
        # Predict
        prediction = self.model.predict(X_scaled)[0]  # -1 (anomaly) or +1 (normal)
        score = self.model.score_samples(X_scaled)[0]  # Anomaly score
        
        is_anomaly = prediction == -1
        # Convert score to 0-1 range (lower = more anomalous)
        normalized_score = 1.0 - ((score - self.model.score_samples(X_scaled).min()) / 
                                  (self.model.score_samples(X_scaled).max() - 
                                   self.model.score_samples(X_scaled).min() + 1e-10))
        
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
                nn.Linear(16, latent_dim * 2)  # Mean and logvar
            )
            
            # Decoder
            self.decoder = nn.Sequential(
                nn.Linear(latent_dim, 16),
                nn.ReLU(),
                nn.Linear(16, input_dim),
                nn.Sigmoid()
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
    """
    
    def __init__(
        self,
        use_isolation_forest: bool = True,
        use_vae: bool = False  # VAE requires more training
    ):
        self.if_detector = IsolationForestDetector() if use_isolation_forest and SKLEARN_AVAILABLE else None
        self.vae_detector = VAEDetector() if use_vae and TORCH_AVAILABLE else None
        
        logger.info(
            f"Unsupervised detector initialized: "
            f"IF={use_isolation_forest}, VAE={use_vae}"
        )
    
    def train(self, features_list: List[Dict[str, float]]):
        """Train both detectors."""
        if self.if_detector:
            self.if_detector.train(features_list)
        
        # VAE training would go here (requires more implementation)
        if self.vae_detector:
            logger.warning("VAE training not yet implemented")
    
    def predict(self, features: Dict[str, float]) -> Dict[str, any]:
        """
        Predict anomaly using ensemble of detectors.
        
        Returns:
            Dict with predictions from all detectors
        """
        results = {}
        
        if self.if_detector:
            is_anomaly, score = self.if_detector.predict(features)
            results['isolation_forest'] = {
                'is_anomaly': is_anomaly,
                'score': score
            }
        
        if self.vae_detector:
            # Convert features to tensor
            feature_array = np.array([[
                features.get('tcp_packets', 0.0),
                features.get('udp_packets', 0.0),
                features.get('icmp_packets', 0.0),
                features.get('syscall_latency', 0.0),
                features.get('packet_loss', 0.0),
                features.get('throughput', 0.0),
                features.get('cpu', 0.0),
                features.get('memory', 0.0),
            ]])
            feature_tensor = torch.FloatTensor(feature_array)
            
            score = self.vae_detector.anomaly_score(feature_tensor)
            results['vae'] = {
                'is_anomaly': score > 0.5,  # Threshold
                'score': score
            }
        
        # Ensemble decision (majority vote or weighted average)
        if len(results) > 1:
            anomaly_votes = sum(1 for r in results.values() if r['is_anomaly'])
            ensemble_anomaly = anomaly_votes >= len(results) / 2
            ensemble_score = np.mean([r['score'] for r in results.values()])
        elif results:
            r = list(results.values())[0]
            ensemble_anomaly = r['is_anomaly']
            ensemble_score = r['score']
        else:
            ensemble_anomaly = False
            ensemble_score = 0.0
        
        results['ensemble'] = {
            'is_anomaly': ensemble_anomaly,
            'score': ensemble_score
        }
        
        return results


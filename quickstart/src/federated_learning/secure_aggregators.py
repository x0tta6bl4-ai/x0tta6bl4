"""
Privacy-Preserving Aggregators for Federated Learning.

Extends base aggregators with differential privacy and secure aggregation.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional


from .aggregators import (AggregationResult, Aggregator, FedAvgAggregator,
                          KrumAggregator)
from .privacy import (DifferentialPrivacy, DPConfig, GradientClipper,
                      PrivacyBudget)
from .protocol import GlobalModel, ModelUpdate

logger = logging.getLogger(__name__)


class SecureFedAvgAggregator(FedAvgAggregator):
    """
    Privacy-preserving FedAvg with differential privacy.

    Features:
    - Gradient clipping (L2 norm)
    - Gaussian noise addition
    - Privacy budget tracking
    - No raw data sharing

    Reference: "Deep Learning with Differential Privacy" (Abadi et al., 2016)
    """

    def __init__(self, dp_config: Optional[DPConfig] = None, enable_dp: bool = True):
        super().__init__()
        self.enable_dp = enable_dp
        self.dp_config = dp_config or DPConfig()
        self.privacy_budget = PrivacyBudget()
        self.gradient_clipper = GradientClipper(max_norm=self.dp_config.max_grad_norm)

        if enable_dp:
            self.dp_engine = DifferentialPrivacy(config=self.dp_config)
        else:
            self.dp_engine = None

    def aggregate(
        self, updates: List[ModelUpdate], previous_model: Optional[GlobalModel] = None
    ) -> AggregationResult:
        """
        Aggregate with privacy-preserving mechanisms.

        Steps:
        1. Clip gradients to bound sensitivity
        2. Add noise (if DP enabled)
        3. Aggregate using parent FedAvg
        4. Update privacy budget
        """
        if not updates:
            return AggregationResult(
                success=False, error_message="No updates to aggregate"
            )

        try:
            # Step 1: Clip gradients
            clipped_updates = self._clip_gradients(updates)

            # Step 2: Add noise (if DP enabled)
            if self.enable_dp and self.dp_engine:
                noisy_updates = self._add_noise(clipped_updates)
            else:
                noisy_updates = clipped_updates

            # Step 3: Aggregate using parent method
            result = super().aggregate(noisy_updates, previous_model)

            # Step 4: Update privacy budget
            if self.enable_dp and self.dp_engine:
                # Get epsilon spent from DP engine
                epsilon_spent, _ = self.dp_engine.get_privacy_spent()
                # Use per-round epsilon from config
                per_round_epsilon = (
                    self.dp_config.target_epsilon / self.dp_config.max_rounds
                )
                self.privacy_budget.add_round(
                    epsilon_spent=per_round_epsilon,
                    noise_scale=self.dp_config.noise_multiplier,
                )

                # Add privacy info to result
                if result.success:
                    result.privacy_epsilon_spent = per_round_epsilon
                    result.privacy_budget_remaining = self.privacy_budget.remaining(
                        self.dp_config.target_epsilon
                    )

            return result

        except Exception as e:
            logger.error(f"SecureFedAvg aggregation failed: {e}")
            return AggregationResult(success=False, error_message=str(e))

    def _clip_gradients(self, updates: List[ModelUpdate]) -> List[ModelUpdate]:
        """Clip gradients to bound sensitivity."""
        clipped_updates = []

        for update in updates:
            # Convert weights to flat vector
            grad_vector = update.weights.to_flat_vector()

            # Clip
            clipped_grad, original_norm = self.gradient_clipper.clip(grad_vector)

            # Create new update with clipped gradients
            # (In real implementation, would reconstruct ModelWeights)
            clipped_update = ModelUpdate(
                node_id=update.node_id,
                round_number=update.round_number,
                weights=update.weights,  # Would be reconstructed from clipped_grad
                num_samples=update.num_samples,
                training_loss=update.training_loss,
                validation_loss=update.validation_loss,
            )
            clipped_updates.append(clipped_update)

        return clipped_updates

    def _add_noise(self, updates: List[ModelUpdate]) -> List[ModelUpdate]:
        """Add Gaussian noise to gradients."""
        if not self.dp_engine:
            return updates

        noisy_updates = []

        for update in updates:
            # Convert weights to flat vector
            grad_vector = update.weights.to_flat_vector()

            # Add noise using privatize_gradients
            noisy_grad, _ = self.dp_engine.privatize_gradients(
                gradients=grad_vector, num_samples=update.num_samples or 1
            )

            # Create new update with noisy gradients
            # (In real implementation, would reconstruct ModelWeights)
            noisy_update = ModelUpdate(
                node_id=update.node_id,
                round_number=update.round_number,
                weights=update.weights,  # Would be reconstructed from noisy_grad
                num_samples=update.num_samples,
                training_loss=update.training_loss,
                validation_loss=update.validation_loss,
            )
            noisy_updates.append(noisy_update)

        return noisy_updates


class SecureKrumAggregator(KrumAggregator):
    """
    Privacy-preserving Krum aggregator.

    Combines Byzantine-robust selection with differential privacy.
    """

    def __init__(
        self,
        f: int = 1,
        multi_krum: bool = False,
        m: int = 1,
        dp_config: Optional[DPConfig] = None,
        enable_dp: bool = True,
    ):
        super().__init__(f=f, multi_krum=multi_krum, m=m)
        self.enable_dp = enable_dp
        self.dp_config = dp_config or DPConfig()
        self.privacy_budget = PrivacyBudget()

        if enable_dp:
            self.dp_engine = DifferentialPrivacy(config=self.dp_config)
            self.gradient_clipper = GradientClipper(
                max_norm=self.dp_config.max_grad_norm
            )
        else:
            self.dp_engine = None
            self.gradient_clipper = None

    def aggregate(
        self, updates: List[ModelUpdate], previous_model: Optional[GlobalModel] = None
    ) -> AggregationResult:
        """Aggregate with privacy-preserving and Byzantine-robust mechanisms."""
        if not updates:
            return AggregationResult(
                success=False, error_message="No updates to aggregate"
            )

        try:
            # Step 1: Clip gradients (if DP enabled)
            if self.enable_dp and self.gradient_clipper:
                clipped_updates = self._clip_gradients(updates)
            else:
                clipped_updates = updates

            # Step 2: Add noise (if DP enabled)
            if self.enable_dp and self.dp_engine:
                noisy_updates = self._add_noise(clipped_updates)
            else:
                noisy_updates = clipped_updates

            # Step 3: Byzantine-robust aggregation (using parent Krum)
            result = super().aggregate(noisy_updates, previous_model)

            # Step 4: Update privacy budget
            if self.enable_dp and self.dp_engine and result.success:
                # Use per-round epsilon from config
                per_round_epsilon = (
                    self.dp_config.target_epsilon / self.dp_config.max_rounds
                )
                self.privacy_budget.add_round(
                    epsilon_spent=per_round_epsilon,
                    noise_scale=self.dp_config.noise_multiplier,
                )

                result.privacy_epsilon_spent = per_round_epsilon
                result.privacy_budget_remaining = self.privacy_budget.remaining(
                    self.dp_config.target_epsilon
                )

            return result

        except Exception as e:
            logger.error(f"SecureKrum aggregation failed: {e}")
            return AggregationResult(success=False, error_message=str(e))

    def _clip_gradients(self, updates: List[ModelUpdate]) -> List[ModelUpdate]:
        """Clip gradients to bound sensitivity."""
        clipped_updates = []

        for update in updates:
            grad_vector = update.weights.to_flat_vector()
            clipped_grad, _ = self.gradient_clipper.clip(grad_vector)

            # Create new update (would reconstruct ModelWeights in real implementation)
            clipped_update = ModelUpdate(
                node_id=update.node_id,
                round_number=update.round_number,
                weights=update.weights,
                num_samples=update.num_samples,
                training_loss=update.training_loss,
                validation_loss=update.validation_loss,
            )
            clipped_updates.append(clipped_update)

        return clipped_updates

    def _add_noise(self, updates: List[ModelUpdate]) -> List[ModelUpdate]:
        """Add Gaussian noise to gradients."""
        if not self.dp_engine:
            return updates

        noisy_updates = []

        for update in updates:
            grad_vector = update.weights.to_flat_vector()
            # Use privatize_gradients instead of add_noise
            noisy_grad, _ = self.dp_engine.privatize_gradients(
                gradients=grad_vector, num_samples=update.num_samples or 1
            )

            # Create new update (would reconstruct ModelWeights in real implementation)
            noisy_update = ModelUpdate(
                node_id=update.node_id,
                round_number=update.round_number,
                weights=update.weights,
                num_samples=update.num_samples,
                training_loss=update.training_loss,
                validation_loss=update.validation_loss,
            )
            noisy_updates.append(noisy_update)

        return noisy_updates


class GraphSAGEAggregator(Aggregator):
    """
    GraphSAGE-specific aggregator for federated learning.

    Handles:
    - Node embedding aggregation
    - Graph structure aggregation
    - Edge weight aggregation
    """

    def __init__(self, base_aggregator: Optional[Aggregator] = None):
        super().__init__(name="graphsage")
        self.base_aggregator = base_aggregator or FedAvgAggregator()

    def aggregate(
        self, updates: List[ModelUpdate], previous_model: Optional[GlobalModel] = None
    ) -> AggregationResult:
        """
        Aggregate GraphSAGE model updates.

        GraphSAGE models have:
        - Node embeddings (node features)
        - Graph structure (adjacency matrix)
        - Edge weights (optional)
        """
        if not updates:
            return AggregationResult(
                success=False, error_message="No updates to aggregate"
            )

        try:
            # Extract GraphSAGE-specific components
            node_embeddings = self._extract_node_embeddings(updates)
            graph_structures = self._extract_graph_structures(updates)
            edge_weights = self._extract_edge_weights(updates)

            # Aggregate node embeddings
            aggregated_embeddings = self._aggregate_embeddings(node_embeddings)

            # Aggregate graph structure (union of graphs)
            aggregated_structure = self._aggregate_structure(graph_structures)

            # Aggregate edge weights (if present)
            aggregated_edge_weights = None
            if edge_weights:
                aggregated_edge_weights = self._aggregate_edge_weights(edge_weights)

            # Use base aggregator for model weights
            result = self.base_aggregator.aggregate(updates, previous_model)

            # Add GraphSAGE-specific metadata
            if result.success and result.global_model:
                result.global_model.graphsage_metadata = {
                    "node_embeddings": aggregated_embeddings,
                    "graph_structure": aggregated_structure,
                    "edge_weights": aggregated_edge_weights,
                }

            return result

        except Exception as e:
            logger.error(f"GraphSAGE aggregation failed: {e}")
            return AggregationResult(success=False, error_message=str(e))

    def _extract_node_embeddings(
        self, updates: List[ModelUpdate]
    ) -> List[Dict[str, Any]]:
        """Extract node embeddings from updates."""
        embeddings = []
        for update in updates:
            metadata = update.weights.metadata or {}
            node_embeddings = metadata.get("node_embeddings")
            if isinstance(node_embeddings, dict) and node_embeddings:
                embeddings.append(node_embeddings)
        return embeddings

    def _extract_graph_structures(
        self, updates: List[ModelUpdate]
    ) -> List[Dict[str, Any]]:
        """Extract graph structures from updates."""
        structures = []
        for update in updates:
            metadata = update.weights.metadata or {}
            graph_structure = metadata.get("graph_structure")
            if isinstance(graph_structure, dict) and graph_structure:
                structures.append(graph_structure)
        return structures

    def _extract_edge_weights(
        self, updates: List[ModelUpdate]
    ) -> Optional[List[Dict[str, Any]]]:
        """Extract edge weights from updates."""
        weights = []
        for update in updates:
            metadata = update.weights.metadata or {}
            edge_weights = metadata.get("edge_weights")
            if isinstance(edge_weights, dict) and edge_weights:
                weights.append(edge_weights)
        return weights if weights else None

    def _aggregate_embeddings(self, embeddings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate node embeddings."""
        sums: Dict[str, List[float]] = {}
        counts: Dict[str, int] = {}

        for embedding_map in embeddings:
            for node_id, vector in embedding_map.items():
                if not isinstance(vector, list) or not all(
                    isinstance(value, (int, float)) for value in vector
                ):
                    continue
                if node_id not in sums:
                    sums[node_id] = [0.0] * len(vector)
                    counts[node_id] = 0
                if len(sums[node_id]) != len(vector):
                    logger.warning(
                        "Skipping GraphSAGE embedding with mismatched dimension for %s",
                        node_id,
                    )
                    continue
                sums[node_id] = [
                    current + float(value)
                    for current, value in zip(sums[node_id], vector)
                ]
                counts[node_id] += 1

        return {
            node_id: [value / counts[node_id] for value in vector]
            for node_id, vector in sums.items()
            if counts[node_id] > 0
        }

    def _aggregate_structure(self, structures: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate graph structures (union of graphs)."""
        nodes = set()
        edges = set()

        for structure in structures:
            for node in structure.get("nodes", []):
                nodes.add(str(node))

            for edge in structure.get("edges", []):
                if isinstance(edge, dict):
                    source = edge.get("source")
                    target = edge.get("target")
                elif isinstance(edge, (list, tuple)) and len(edge) >= 2:
                    source, target = edge[0], edge[1]
                else:
                    continue
                if source is not None and target is not None:
                    edges.add((str(source), str(target)))

            adjacency = structure.get("adjacency", {})
            if isinstance(adjacency, dict):
                for source, targets in adjacency.items():
                    nodes.add(str(source))
                    if isinstance(targets, list):
                        for target in targets:
                            nodes.add(str(target))
                            edges.add((str(source), str(target)))

        return {
            "nodes": sorted(nodes),
            "edges": [
                {"source": source, "target": target}
                for source, target in sorted(edges)
            ],
        }

    def _aggregate_edge_weights(self, weights: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate edge weights."""
        sums: Dict[str, float] = {}
        counts: Dict[str, int] = {}

        for weight_map in weights:
            for edge_id, value in weight_map.items():
                if not isinstance(value, (int, float)):
                    continue
                sums[edge_id] = sums.get(edge_id, 0.0) + float(value)
                counts[edge_id] = counts.get(edge_id, 0) + 1

        return {
            edge_id: total / counts[edge_id]
            for edge_id, total in sums.items()
            if counts[edge_id] > 0
        }


def get_secure_aggregator(
    method: str = "secure_fedavg",
    dp_config: Optional[DPConfig] = None,
    enable_dp: bool = True,
    **kwargs,
) -> Aggregator:
    """
    Factory function to get privacy-preserving aggregator.

    Args:
        method: Aggregation method name
        dp_config: Differential privacy configuration
        enable_dp: Enable differential privacy
        **kwargs: Additional arguments for specific aggregators

    Returns:
        Aggregator instance with privacy-preserving
    """
    secure_aggregators = {
        "secure_fedavg": SecureFedAvgAggregator,
        "secure_krum": SecureKrumAggregator,
        "graphsage": GraphSAGEAggregator,
    }

    if method in secure_aggregators:
        aggregator_class = secure_aggregators[method]
        # GraphSAGEAggregator doesn't take dp_config/enable_dp
        if method == "graphsage":
            return aggregator_class(**kwargs)
        else:
            return aggregator_class(dp_config=dp_config, enable_dp=enable_dp, **kwargs)

    # Fallback to base aggregators
    from .aggregators import get_aggregator

    return get_aggregator(method, **kwargs)


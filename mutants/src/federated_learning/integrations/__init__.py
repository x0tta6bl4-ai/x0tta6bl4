"""
Federated Learning Integrations.

Connects FL components with other x0tta6bl4 modules:
- Digital Twin integration for realistic simulation
- Coordinator-Consensus bridge
- Privacy-aware aggregation pipeline
- Blockchain audit trail
"""

from .twin_integration import (
    TwinBackedRoutingEnv,
    FederatedTrainingOrchestrator,
    TwinMetricsCollector
)

__all__ = [
    "TwinBackedRoutingEnv",
    "FederatedTrainingOrchestrator",
    "TwinMetricsCollector"
]

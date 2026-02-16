"""
Federated Learning Module for x0tta6bl4 Mesh.

Implements BE-AFPPO (Blockchain-Empowered Asynchronous Federated PPO)
for distributed mesh routing optimization.

Components:
- Protocol: Message types and signatures
- Coordinator: Async FL orchestration
- Aggregators: Byzantine-robust aggregation (Krum, Trimmed Mean)
- Privacy: Differential Privacy for gradients
- Consensus: DG-PBFT for model updates
- Agent: PPO for routing decisions
"""

from .aggregators import (Aggregator, FedAvgAggregator, KrumAggregator,
                          MedianAggregator, TrimmedMeanAggregator,
                          get_aggregator)
from .blockchain import (Block, BlockType, ConsensusProof, ModelBlockchain,
                         ModelMetadata, WeightStorage,
                         create_genesis_blockchain)
from .consensus import (ConsensusMessage, ConsensusNetwork, ConsensusPhase,
                        ConsensusProposal, PBFTConfig, PBFTConsensus)
from .coordinator import (CoordinatorConfig, FederatedCoordinator, NodeStatus,
                          TrainingRound)
from .ppo_agent import (MeshRoutingEnv, MeshState, PPOAgent, PPOConfig,
                        TrajectoryBuffer, train_ppo)
from .privacy import (DifferentialPrivacy, DPConfig, GradientClipper,
                      PrivacyBudget, SecureAggregation)
from .protocol import (AggregationResult, FLMessage, FLMessageType,
                       GlobalModel, ModelUpdate, ModelWeights, SignedMessage)

__all__ = [
    # Protocol
    "ModelUpdate",
    "GlobalModel",
    "ModelWeights",
    "FLMessage",
    "FLMessageType",
    "SignedMessage",
    "AggregationResult",
    # Aggregators
    "Aggregator",
    "FedAvgAggregator",
    "KrumAggregator",
    "TrimmedMeanAggregator",
    "MedianAggregator",
    "get_aggregator",
    # Coordinator
    "FederatedCoordinator",
    "CoordinatorConfig",
    "TrainingRound",
    "NodeStatus",
    # Privacy
    "DifferentialPrivacy",
    "DPConfig",
    "PrivacyBudget",
    "GradientClipper",
    "SecureAggregation",
    # Consensus
    "PBFTConsensus",
    "PBFTConfig",
    "ConsensusMessage",
    "ConsensusProposal",
    "ConsensusPhase",
    "ConsensusNetwork",
    # PPO Agent
    "PPOAgent",
    "PPOConfig",
    "MeshRoutingEnv",
    "MeshState",
    "TrajectoryBuffer",
    "train_ppo",
    # Blockchain
    "ModelBlockchain",
    "Block",
    "BlockType",
    "ModelMetadata",
    "WeightStorage",
    "create_genesis_blockchain",
]

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

from .protocol import (
    ModelUpdate,
    GlobalModel,
    ModelWeights,
    FLMessage,
    FLMessageType,
    SignedMessage,
    AggregationResult
)

from .aggregators import (
    Aggregator,
    FedAvgAggregator,
    KrumAggregator,
    TrimmedMeanAggregator,
    MedianAggregator,
    get_aggregator
)

from .coordinator import (
    FederatedCoordinator,
    CoordinatorConfig,
    TrainingRound,
    NodeStatus
)

from .privacy import (
    DifferentialPrivacy,
    DPConfig,
    PrivacyBudget,
    GradientClipper,
    SecureAggregation
)

from .consensus import (
    PBFTConsensus,
    PBFTConfig,
    ConsensusMessage,
    ConsensusProposal,
    ConsensusPhase,
    ConsensusNetwork
)

from .ppo_agent import (
    PPOAgent,
    PPOConfig,
    MeshRoutingEnv,
    MeshState,
    TrajectoryBuffer,
    train_ppo
)

from .blockchain import (
    ModelBlockchain,
    Block,
    BlockType,
    ModelMetadata,
    ConsensusProof,
    WeightStorage,
    create_genesis_blockchain
)

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
    "create_genesis_blockchain"
]

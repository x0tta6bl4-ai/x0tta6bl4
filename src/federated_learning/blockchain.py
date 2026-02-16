"""
Model Blockchain for Federated Learning.

Provides immutable audit trail for FL model updates.
Enables model provenance, rollback, and compliance auditing.

Features:
- Hash-chained blocks for tamper detection
- PBFT consensus proofs
- Model version management
- Lightweight IPFS-style content addressing
"""

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class BlockType(Enum):
    """Types of blocks in the model blockchain."""

    GENESIS = "genesis"
    MODEL_UPDATE = "model_update"
    AGGREGATION = "aggregation"
    CHECKPOINT = "checkpoint"
    ROLLBACK = "rollback"


@dataclass
class ConsensusProof:
    """Proof of PBFT consensus for a block."""

    view: int
    sequence: int
    num_prepares: int
    num_commits: int
    quorum_reached: bool
    participants: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "view": self.view,
            "sequence": self.sequence,
            "num_prepares": self.num_prepares,
            "num_commits": self.num_commits,
            "quorum_reached": self.quorum_reached,
            "participants": self.participants,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConsensusProof":
        return cls(**data)


@dataclass
class ModelMetadata:
    """Metadata for a model version."""

    version: int
    round_number: int
    contributors: List[str]
    aggregation_method: str
    total_samples: int

    # Performance metrics
    avg_training_loss: float = 0.0
    avg_validation_loss: float = 0.0

    # Privacy info
    epsilon_spent: float = 0.0
    delta: float = 1e-5

    # Byzantine info
    suspected_byzantine: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "round_number": self.round_number,
            "contributors": self.contributors,
            "aggregation_method": self.aggregation_method,
            "total_samples": self.total_samples,
            "avg_training_loss": self.avg_training_loss,
            "avg_validation_loss": self.avg_validation_loss,
            "epsilon_spent": self.epsilon_spent,
            "delta": self.delta,
            "suspected_byzantine": self.suspected_byzantine,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModelMetadata":
        return cls(**data)


@dataclass
class Block:
    """
    A block in the model blockchain.

    Contains model update info, consensus proof, and hash chain link.
    """

    index: int
    block_type: BlockType
    timestamp: float

    # Content
    weights_hash: str  # Content-addressed hash of model weights
    metadata: Optional[ModelMetadata] = None
    consensus_proof: Optional[ConsensusProof] = None

    # Chain links
    previous_hash: str = ""
    block_hash: str = ""

    # Additional data
    data: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.block_hash:
            self.block_hash = self.compute_hash()

    def compute_hash(self) -> str:
        """Compute SHA-256 hash of block contents."""
        content = {
            "index": self.index,
            "block_type": self.block_type.value,
            "timestamp": self.timestamp,
            "weights_hash": self.weights_hash,
            "metadata": self.metadata.to_dict() if self.metadata else None,
            "consensus_proof": (
                self.consensus_proof.to_dict() if self.consensus_proof else None
            ),
            "previous_hash": self.previous_hash,
            "data": self.data,
        }
        content_bytes = json.dumps(content, sort_keys=True).encode()
        return hashlib.sha256(content_bytes).hexdigest()

    def verify_hash(self) -> bool:
        """Verify block hash integrity."""
        return self.block_hash == self.compute_hash()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "block_type": self.block_type.value,
            "timestamp": self.timestamp,
            "weights_hash": self.weights_hash,
            "metadata": self.metadata.to_dict() if self.metadata else None,
            "consensus_proof": (
                self.consensus_proof.to_dict() if self.consensus_proof else None
            ),
            "previous_hash": self.previous_hash,
            "block_hash": self.block_hash,
            "data": self.data,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Block":
        metadata = None
        if data.get("metadata"):
            metadata = ModelMetadata.from_dict(data["metadata"])

        consensus_proof = None
        if data.get("consensus_proof"):
            consensus_proof = ConsensusProof.from_dict(data["consensus_proof"])

        return cls(
            index=data["index"],
            block_type=BlockType(data["block_type"]),
            timestamp=data["timestamp"],
            weights_hash=data["weights_hash"],
            metadata=metadata,
            consensus_proof=consensus_proof,
            previous_hash=data["previous_hash"],
            block_hash=data["block_hash"],
            data=data.get("data", {}),
        )


class WeightStorage:
    """
    Content-addressed storage for model weights.

    Simulates IPFS-style storage with content hashing.
    In production, integrate with actual IPFS or S3.
    """

    def __init__(self):
        self._storage: Dict[str, List[float]] = {}

    def store(self, weights: List[float]) -> str:
        """
        Store weights and return content hash.

        Args:
            weights: Model weight vector

        Returns:
            Content hash (CID-like)
        """
        # Compute content hash
        import struct

        data = struct.pack(f"{len(weights)}f", *weights)
        content_hash = hashlib.sha256(data).hexdigest()

        # Store
        self._storage[content_hash] = weights

        return content_hash

    def retrieve(self, content_hash: str) -> Optional[List[float]]:
        """
        Retrieve weights by content hash.

        Args:
            content_hash: Content hash from store()

        Returns:
            Weight vector or None if not found
        """
        return self._storage.get(content_hash)

    def verify(self, content_hash: str, weights: List[float]) -> bool:
        """Verify weights match their hash."""
        import struct

        data = struct.pack(f"{len(weights)}f", *weights)
        computed_hash = hashlib.sha256(data).hexdigest()
        return computed_hash == content_hash

    def contains(self, content_hash: str) -> bool:
        """Check if hash exists in storage."""
        return content_hash in self._storage

    def size(self) -> int:
        """Number of stored weight sets."""
        return len(self._storage)


class ModelBlockchain:
    """
    Blockchain for FL model provenance.

    Features:
    - Immutable audit trail
    - Tamper detection via hash chain
    - Consensus proof integration
    - Model rollback capability
    """

    def __init__(self, chain_id: str = "x0tta6bl4-fl"):
        self.chain_id = chain_id
        self.chain: List[Block] = []
        self.weight_storage = WeightStorage()

        # Index for quick lookups
        self._version_to_block: Dict[int, int] = {}  # version -> block index
        self._hash_to_block: Dict[str, int] = {}  # block_hash -> block index

        # Create genesis block
        self._create_genesis()

        logger.info(f"ModelBlockchain '{chain_id}' initialized")

    def _create_genesis(self) -> None:
        """Create genesis block."""
        genesis = Block(
            index=0,
            block_type=BlockType.GENESIS,
            timestamp=time.time(),
            weights_hash="0" * 64,
            previous_hash="0" * 64,
            data={"chain_id": self.chain_id, "created": time.time()},
        )
        self.chain.append(genesis)
        self._hash_to_block[genesis.block_hash] = 0

    def add_model_update(
        self,
        weights: List[float],
        metadata: ModelMetadata,
        consensus_proof: Optional[ConsensusProof] = None,
    ) -> Block:
        """
        Add new model update to the chain.

        Args:
            weights: Model weight vector
            metadata: Model metadata
            consensus_proof: PBFT consensus proof

        Returns:
            Created block
        """
        # Store weights
        weights_hash = self.weight_storage.store(weights)

        # Create block
        block = Block(
            index=len(self.chain),
            block_type=BlockType.MODEL_UPDATE,
            timestamp=time.time(),
            weights_hash=weights_hash,
            metadata=metadata,
            consensus_proof=consensus_proof,
            previous_hash=self.chain[-1].block_hash,
        )

        # Add to chain
        self.chain.append(block)
        self._version_to_block[metadata.version] = block.index
        self._hash_to_block[block.block_hash] = block.index

        logger.info(
            f"Model v{metadata.version} added to blockchain: "
            f"block={block.index}, hash={block.block_hash[:16]}"
        )

        return block

    def add_checkpoint(
        self, weights: List[float], version: int, description: str = ""
    ) -> Block:
        """Add a checkpoint block."""
        weights_hash = self.weight_storage.store(weights)

        block = Block(
            index=len(self.chain),
            block_type=BlockType.CHECKPOINT,
            timestamp=time.time(),
            weights_hash=weights_hash,
            previous_hash=self.chain[-1].block_hash,
            data={"version": version, "description": description},
        )

        self.chain.append(block)
        self._hash_to_block[block.block_hash] = block.index

        logger.info(f"Checkpoint created: block={block.index}")

        return block

    def add_rollback(self, target_version: int, reason: str = "") -> Optional[Block]:
        """
        Add rollback block pointing to previous version.

        Args:
            target_version: Version to rollback to
            reason: Reason for rollback

        Returns:
            Rollback block or None if target not found
        """
        if target_version not in self._version_to_block:
            logger.warning(f"Cannot rollback: version {target_version} not found")
            return None

        target_block_idx = self._version_to_block[target_version]
        target_block = self.chain[target_block_idx]

        block = Block(
            index=len(self.chain),
            block_type=BlockType.ROLLBACK,
            timestamp=time.time(),
            weights_hash=target_block.weights_hash,
            previous_hash=self.chain[-1].block_hash,
            data={
                "target_version": target_version,
                "target_block": target_block_idx,
                "reason": reason,
            },
        )

        self.chain.append(block)
        self._hash_to_block[block.block_hash] = block.index

        logger.info(f"Rollback to v{target_version}: reason='{reason}'")

        return block

    def get_model_weights(self, version: int) -> Optional[List[float]]:
        """Get model weights for a specific version."""
        if version not in self._version_to_block:
            return None

        block_idx = self._version_to_block[version]
        block = self.chain[block_idx]

        return self.weight_storage.retrieve(block.weights_hash)

    def get_latest_weights(self) -> Optional[List[float]]:
        """Get weights from the latest model update."""
        for block in reversed(self.chain):
            if block.block_type in (BlockType.MODEL_UPDATE, BlockType.ROLLBACK):
                return self.weight_storage.retrieve(block.weights_hash)
        return None

    def get_block(self, index: int) -> Optional[Block]:
        """Get block by index."""
        if 0 <= index < len(self.chain):
            return self.chain[index]
        return None

    def get_block_by_hash(self, block_hash: str) -> Optional[Block]:
        """Get block by hash."""
        if block_hash in self._hash_to_block:
            return self.chain[self._hash_to_block[block_hash]]
        return None

    def verify_chain(self) -> Tuple[bool, List[str]]:
        """
        Verify integrity of the entire chain.

        Returns:
            Tuple of (is_valid, list of errors)
        """
        errors = []

        for i, block in enumerate(self.chain):
            # Verify block hash
            if not block.verify_hash():
                errors.append(f"Block {i}: hash mismatch")

            # Verify chain link (except genesis)
            if i > 0:
                if block.previous_hash != self.chain[i - 1].block_hash:
                    errors.append(f"Block {i}: broken chain link")

            # Verify weights exist
            if block.block_type != BlockType.GENESIS:
                if not self.weight_storage.contains(block.weights_hash):
                    errors.append(f"Block {i}: missing weights")

        is_valid = len(errors) == 0

        if is_valid:
            logger.info("Chain verification passed")
        else:
            logger.warning(f"Chain verification failed: {errors}")

        return is_valid, errors

    def get_model_history(self) -> List[Dict[str, Any]]:
        """Get history of model updates."""
        history = []

        for block in self.chain:
            if block.block_type == BlockType.MODEL_UPDATE:
                history.append(
                    {
                        "block_index": block.index,
                        "version": block.metadata.version if block.metadata else 0,
                        "round": block.metadata.round_number if block.metadata else 0,
                        "contributors": (
                            len(block.metadata.contributors) if block.metadata else 0
                        ),
                        "timestamp": block.timestamp,
                        "block_hash": block.block_hash[:16],
                    }
                )

        return history

    def get_provenance(self, version: int) -> List[Dict[str, Any]]:
        """
        Get full provenance chain for a model version.

        Returns chain of blocks from genesis to specified version.
        """
        if version not in self._version_to_block:
            return []

        target_idx = self._version_to_block[version]
        provenance = []

        for i in range(target_idx + 1):
            block = self.chain[i]
            provenance.append(
                {
                    "index": block.index,
                    "type": block.block_type.value,
                    "timestamp": block.timestamp,
                    "hash": block.block_hash[:16],
                }
            )

        return provenance

    def export_chain(self) -> Dict[str, Any]:
        """Export entire chain as JSON-serializable dict."""
        return {
            "chain_id": self.chain_id,
            "length": len(self.chain),
            "blocks": [block.to_dict() for block in self.chain],
            "versions": list(self._version_to_block.keys()),
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get blockchain statistics."""
        model_updates = sum(
            1 for b in self.chain if b.block_type == BlockType.MODEL_UPDATE
        )
        rollbacks = sum(1 for b in self.chain if b.block_type == BlockType.ROLLBACK)
        checkpoints = sum(1 for b in self.chain if b.block_type == BlockType.CHECKPOINT)

        return {
            "chain_id": self.chain_id,
            "chain_length": len(self.chain),
            "model_updates": model_updates,
            "rollbacks": rollbacks,
            "checkpoints": checkpoints,
            "stored_weights": self.weight_storage.size(),
            "latest_version": (
                max(self._version_to_block.keys()) if self._version_to_block else 0
            ),
        }


def create_genesis_blockchain(
    initial_weights: List[float], chain_id: str = "x0tta6bl4-fl"
) -> ModelBlockchain:
    """
    Create a new blockchain with initial model.

    Args:
        initial_weights: Initial model weights
        chain_id: Chain identifier

    Returns:
        Initialized blockchain
    """
    blockchain = ModelBlockchain(chain_id)

    # Add initial model as first update
    metadata = ModelMetadata(
        version=0,
        round_number=0,
        contributors=["initializer"],
        aggregation_method="initial",
        total_samples=0,
    )

    blockchain.add_model_update(initial_weights, metadata)

    return blockchain

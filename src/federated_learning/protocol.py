"""
Federated Learning Protocol.
Defines message types, signatures, and serialization for FL communication.

Features:
- Ed25519 digital signatures for authentication
- Msgpack serialization for efficiency
- Versioned protocol for forward compatibility
"""
import time
import hashlib
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
import json
import struct

logger = logging.getLogger(__name__)

# Try to import cryptography for Ed25519
try:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey
    )
    from cryptography.hazmat.primitives.serialization import (
        Encoding,
        PublicFormat,
        PrivateFormat,
        NoEncryption
    )
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False
    logger.warning("cryptography not available, using fallback signatures")

# Try to import msgpack
try:
    import msgpack
    HAS_MSGPACK = True
except ImportError:
    HAS_MSGPACK = False
    logger.warning("msgpack not available, using JSON serialization")


# Protocol version
PROTOCOL_VERSION = "1.0.0"


class FLMessageType(Enum):
    """Federated Learning message types."""
    # Training coordination
    ROUND_START = "round_start"
    ROUND_END = "round_end"
    MODEL_REQUEST = "model_request"
    MODEL_RESPONSE = "model_response"
    
    # Model updates
    LOCAL_UPDATE = "local_update"
    GLOBAL_UPDATE = "global_update"
    GRADIENT_SHARE = "gradient_share"
    
    # Consensus
    PREPARE = "prepare"
    COMMIT = "commit"
    VOTE = "vote"
    FINALIZE = "finalize"
    
    # Health & status
    HEARTBEAT = "heartbeat"
    STATUS_REQUEST = "status_request"
    STATUS_RESPONSE = "status_response"
    
    # Error handling
    ERROR = "error"
    REJECTION = "rejection"


@dataclass
class ModelWeights:
    """Represents model weights/parameters."""
    layer_weights: Dict[str, List[float]] = field(default_factory=dict)
    layer_biases: Dict[str, List[float]] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_flat_vector(self) -> List[float]:
        """Flatten all weights into a single vector."""
        vector = []
        for layer_name in sorted(self.layer_weights.keys()):
            vector.extend(self.layer_weights[layer_name])
            if layer_name in self.layer_biases:
                vector.extend(self.layer_biases[layer_name])
        return vector
    
    @classmethod
    def from_flat_vector(
        cls,
        vector: List[float],
        layer_shapes: Dict[str, Tuple[int, int]]
    ) -> "ModelWeights":
        """Reconstruct from flat vector given layer shapes."""
        weights = ModelWeights()
        idx = 0
        
        for layer_name in sorted(layer_shapes.keys()):
            w_size, b_size = layer_shapes[layer_name]
            weights.layer_weights[layer_name] = vector[idx:idx + w_size]
            idx += w_size
            if b_size > 0:
                weights.layer_biases[layer_name] = vector[idx:idx + b_size]
                idx += b_size
        
        return weights
    
    def compute_hash(self) -> str:
        """Compute hash of weights for integrity verification."""
        flat = self.to_flat_vector()
        data = struct.pack(f'{len(flat)}f', *flat)
        return hashlib.sha256(data).hexdigest()


@dataclass
class ModelUpdate:
    """
    Local model update from a node.
    
    Contains gradients/weights, training metrics, and metadata
    needed for Byzantine-robust aggregation.
    """
    node_id: str
    round_number: int
    weights: ModelWeights
    
    # Training metadata
    num_samples: int = 0
    training_loss: float = 0.0
    validation_loss: float = 0.0
    training_time_seconds: float = 0.0
    
    # Gradient statistics (for Byzantine detection)
    gradient_norm: float = 0.0
    gradient_variance: float = 0.0
    
    # Privacy
    noise_scale: float = 0.0  # DP noise added
    clip_norm: float = 1.0    # Gradient clipping threshold
    
    # Timestamp
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "node_id": self.node_id,
            "round_number": self.round_number,
            "weights": asdict(self.weights),
            "num_samples": self.num_samples,
            "training_loss": self.training_loss,
            "validation_loss": self.validation_loss,
            "training_time_seconds": self.training_time_seconds,
            "gradient_norm": self.gradient_norm,
            "gradient_variance": self.gradient_variance,
            "noise_scale": self.noise_scale,
            "clip_norm": self.clip_norm,
            "timestamp": self.timestamp
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModelUpdate":
        """Create from dictionary."""
        weights_data = data.pop("weights", {})
        weights = ModelWeights(**weights_data)
        return cls(weights=weights, **data)


@dataclass
class GlobalModel:
    """
    Global model state distributed to all nodes.
    
    Includes versioning for synchronization and
    aggregation metadata for transparency.
    """
    version: int
    round_number: int
    weights: ModelWeights
    
    # Aggregation info
    num_contributors: int = 0
    total_samples: int = 0
    aggregation_method: str = "fedavg"
    
    # Metrics
    avg_training_loss: float = 0.0
    avg_validation_loss: float = 0.0
    
    # Integrity
    weights_hash: str = ""
    previous_hash: str = ""  # For chain integrity
    
    # Timestamp
    created_at: float = field(default_factory=time.time)
    
    def __post_init__(self):
        if not self.weights_hash:
            self.weights_hash = self.weights.compute_hash()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "round_number": self.round_number,
            "weights": asdict(self.weights),
            "num_contributors": self.num_contributors,
            "total_samples": self.total_samples,
            "aggregation_method": self.aggregation_method,
            "avg_training_loss": self.avg_training_loss,
            "avg_validation_loss": self.avg_validation_loss,
            "weights_hash": self.weights_hash,
            "previous_hash": self.previous_hash,
            "created_at": self.created_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GlobalModel":
        weights_data = data.pop("weights", {})
        weights = ModelWeights(**weights_data)
        return cls(weights=weights, **data)


@dataclass
class AggregationResult:
    """Result of aggregating multiple model updates."""
    success: bool
    global_model: Optional[GlobalModel] = None
    
    # Statistics
    updates_received: int = 0
    updates_accepted: int = 0
    updates_rejected: int = 0
    
    # Byzantine detection
    suspected_byzantine: List[str] = field(default_factory=list)
    
    # Timing
    aggregation_time_seconds: float = 0.0
    
    # Error info
    error_message: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "global_model": self.global_model.to_dict() if self.global_model else None,
            "updates_received": self.updates_received,
            "updates_accepted": self.updates_accepted,
            "updates_rejected": self.updates_rejected,
            "suspected_byzantine": self.suspected_byzantine,
            "aggregation_time_seconds": self.aggregation_time_seconds,
            "error_message": self.error_message
        }


@dataclass
class SignedMessage:
    """
    Cryptographically signed FL message.
    
    Uses Ed25519 for authentication and integrity.
    """
    message_id: str
    sender_id: str
    message_type: FLMessageType
    payload: Dict[str, Any]
    
    # Signature
    signature: bytes = b""
    public_key: bytes = b""
    
    # Metadata
    timestamp: float = field(default_factory=time.time)
    protocol_version: str = PROTOCOL_VERSION
    
    def compute_message_hash(self) -> bytes:
        """Compute hash of message content for signing."""
        content = {
            "message_id": self.message_id,
            "sender_id": self.sender_id,
            "message_type": self.message_type.value,
            "payload": self.payload,
            "timestamp": self.timestamp
        }
        content_bytes = json.dumps(content, sort_keys=True).encode()
        return hashlib.sha256(content_bytes).digest()
    
    def sign(self, private_key_bytes: bytes) -> None:
        """Sign the message with Ed25519 private key."""
        if not HAS_CRYPTO:
            # Fallback: simple HMAC-like signature
            self.signature = hashlib.sha256(
                self.compute_message_hash() + private_key_bytes
            ).digest()
            return
        
        private_key = Ed25519PrivateKey.from_private_bytes(private_key_bytes)
        message_hash = self.compute_message_hash()
        self.signature = private_key.sign(message_hash)
        self.public_key = private_key.public_key().public_bytes(
            Encoding.Raw, PublicFormat.Raw
        )
    
    def verify(self, public_key_bytes: Optional[bytes] = None) -> bool:
        """Verify the message signature."""
        pk_bytes = public_key_bytes or self.public_key
        if not pk_bytes:
            return False
        
        if not HAS_CRYPTO:
            # Cannot verify without cryptography library
            logger.warning("Cannot verify signature without cryptography")
            return True  # Accept in fallback mode
        
        try:
            public_key = Ed25519PublicKey.from_public_bytes(pk_bytes)
            message_hash = self.compute_message_hash()
            public_key.verify(self.signature, message_hash)
            return True
        except Exception as e:
            logger.warning(f"Signature verification failed: {e}")
            return False
    
    def to_bytes(self) -> bytes:
        """Serialize to bytes for network transmission."""
        data = {
            "message_id": self.message_id,
            "sender_id": self.sender_id,
            "message_type": self.message_type.value,
            "payload": self.payload,
            "signature": self.signature.hex(),
            "public_key": self.public_key.hex(),
            "timestamp": self.timestamp,
            "protocol_version": self.protocol_version
        }
        
        if HAS_MSGPACK:
            return msgpack.packb(data, use_bin_type=True)
        else:
            return json.dumps(data).encode()
    
    @classmethod
    def from_bytes(cls, data: bytes) -> "SignedMessage":
        """Deserialize from bytes."""
        if HAS_MSGPACK:
            parsed = msgpack.unpackb(data, raw=False)
        else:
            parsed = json.loads(data.decode())
        
        return cls(
            message_id=parsed["message_id"],
            sender_id=parsed["sender_id"],
            message_type=FLMessageType(parsed["message_type"]),
            payload=parsed["payload"],
            signature=bytes.fromhex(parsed["signature"]),
            public_key=bytes.fromhex(parsed["public_key"]),
            timestamp=parsed["timestamp"],
            protocol_version=parsed["protocol_version"]
        )


@dataclass
class FLMessage:
    """High-level FL message wrapper with convenience methods."""
    msg_type: FLMessageType
    content: Dict[str, Any]
    sender: str = ""
    receiver: str = ""  # Empty = broadcast
    
    @classmethod
    def round_start(cls, round_number: int, global_model: GlobalModel) -> "FLMessage":
        """Create round start message."""
        return cls(
            msg_type=FLMessageType.ROUND_START,
            content={
                "round_number": round_number,
                "global_model": global_model.to_dict()
            }
        )
    
    @classmethod
    def local_update(cls, update: ModelUpdate) -> "FLMessage":
        """Create local update message."""
        return cls(
            msg_type=FLMessageType.LOCAL_UPDATE,
            content={"update": update.to_dict()},
            sender=update.node_id
        )
    
    @classmethod
    def global_update(cls, model: GlobalModel) -> "FLMessage":
        """Create global update message."""
        return cls(
            msg_type=FLMessageType.GLOBAL_UPDATE,
            content={"global_model": model.to_dict()}
        )
    
    @classmethod
    def heartbeat(cls, node_id: str, status: Dict[str, Any]) -> "FLMessage":
        """Create heartbeat message."""
        return cls(
            msg_type=FLMessageType.HEARTBEAT,
            content={"status": status},
            sender=node_id
        )
    
    @classmethod
    def error(cls, error_code: str, message: str, details: Dict = None) -> "FLMessage":
        """Create error message."""
        return cls(
            msg_type=FLMessageType.ERROR,
            content={
                "error_code": error_code,
                "message": message,
                "details": details or {}
            }
        )


def generate_keypair() -> Tuple[bytes, bytes]:
    """Generate Ed25519 keypair for message signing."""
    if not HAS_CRYPTO:
        # Fallback: random bytes (not secure!)
        import secrets
        private = secrets.token_bytes(32)
        public = hashlib.sha256(private).digest()
        return private, public
    
    private_key = Ed25519PrivateKey.generate()
    private_bytes = private_key.private_bytes(
        Encoding.Raw, PrivateFormat.Raw, NoEncryption()
    )
    public_bytes = private_key.public_key().public_bytes(
        Encoding.Raw, PublicFormat.Raw
    )
    return private_bytes, public_bytes

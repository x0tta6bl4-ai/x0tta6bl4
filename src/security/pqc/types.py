"""
PQC Data Types.

Data classes for Post-Quantum Cryptography operations.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional


class PQCAlgorithm(Enum):
    """Supported PQC algorithms."""
    # Key Encapsulation Mechanisms (NIST FIPS 203)
    ML_KEM_512 = "ML-KEM-512"
    ML_KEM_768 = "ML-KEM-768"
    ML_KEM_1024 = "ML-KEM-1024"
    
    # Digital Signature Algorithms (NIST FIPS 204)
    ML_DSA_44 = "ML-DSA-44"
    ML_DSA_65 = "ML-DSA-65"
    ML_DSA_87 = "ML-DSA-87"


class PQCStatus(Enum):
    """PQC operation status."""
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    ERROR = "error"
    FALLBACK = "fallback"


@dataclass
class PQCKeyPair:
    """PQC key pair for KEM or DSA operations."""
    algorithm: str  # "ML-KEM-768" or "ML-DSA-65"
    public_key: bytes
    secret_key: bytes
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    key_id: str = ""
    
    def __post_init__(self):
        """Generate key_id if not provided."""
        if not self.key_id:
            import hashlib
            # Ensure public_key is bytes
            pk = self.public_key if isinstance(self.public_key, bytes) else bytes(self.public_key)
            self.key_id = hashlib.sha256(pk).hexdigest()[:16]
    
    def is_expired(self) -> bool:
        """Check if key is expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at
    
    def is_valid(self) -> bool:
        """Check if key is valid (not expired and has required fields)."""
        return (
            not self.is_expired()
            and bool(self.public_key)
            and bool(self.secret_key)
            and bool(self.algorithm)
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "algorithm": self.algorithm,
            "public_key_hex": self.public_key.hex(),
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "key_id": self.key_id,
            "is_expired": self.is_expired(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PQCKeyPair':
        """Create from dictionary."""
        return cls(
            algorithm=data["algorithm"],
            public_key=bytes.fromhex(data["public_key_hex"]),
            secret_key=bytes.fromhex(data["secret_key_hex"]) if "secret_key_hex" in data else b"",
            created_at=datetime.fromisoformat(data["created_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None,
            key_id=data.get("key_id", ""),
        )


@dataclass
class PQCSignature:
    """PQC digital signature."""
    algorithm: str  # "ML-DSA-65"
    signature_bytes: bytes
    message_hash: bytes
    timestamp: datetime = field(default_factory=datetime.utcnow)
    signer_key_id: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "algorithm": self.algorithm,
            "signature_hex": self.signature_bytes.hex(),
            "message_hash_hex": self.message_hash.hex(),
            "timestamp": self.timestamp.isoformat(),
            "signer_key_id": self.signer_key_id,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PQCSignature':
        """Create from dictionary."""
        return cls(
            algorithm=data["algorithm"],
            signature_bytes=bytes.fromhex(data["signature_hex"]),
            message_hash=bytes.fromhex(data["message_hash_hex"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            signer_key_id=data.get("signer_key_id", ""),
        )


@dataclass
class PQCEncapsulationResult:
    """Result of KEM encapsulation."""
    ciphertext: bytes
    shared_secret: bytes
    algorithm: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "algorithm": self.algorithm,
            "ciphertext_len": len(self.ciphertext),
            "shared_secret_len": len(self.shared_secret),
        }


@dataclass
class PQCSession:
    """PQC secure session."""
    session_id: str
    algorithm: str
    shared_secret: bytes
    peer_public_key: bytes
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    
    def is_expired(self) -> bool:
        """Check if session is expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (without secret)."""
        return {
            "session_id": self.session_id,
            "algorithm": self.algorithm,
            "peer_public_key_hex": self.peer_public_key.hex(),
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }

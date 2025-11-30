"""
Zero Trust Security Module.
Complete Zero Trust implementation for x0tta6bl4 Mesh.

Components:
- ZKP Authentication (Schnorr, Pedersen)
- Device Attestation (Privacy-preserving)
- Post-Quantum Cryptography (NTRU Hybrid)
- Decentralized Identity (DIDs)
- Threat Intelligence (Distributed)
- Auto-Isolation (Circuit Breaker)
- Policy Engine (ABAC)
- Continuous Verification
"""

from .zero_trust import ZeroTrustValidator
from .zkp_auth import (
    SchnorrZKP,
    PedersenCommitment,
    ZKPAuthenticator,
    ZKPChallenge,
    ZKPProof
)
from .device_attestation import (
    DeviceAttestor,
    AdaptiveTrustManager,
    MeshDeviceAttestor,
    TrustLevel,
    TrustScore,
    AttestationType
)
from .post_quantum import (
    SimplifiedNTRU,
    HybridEncryption,
    QuantumSafeKeyExchange,
    PQMeshSecurity,
    PQAlgorithm
)
from .decentralized_identity import (
    DIDManager,
    DIDResolver,
    DIDDocument,
    VerifiableCredential,
    DIDMethod,
    MeshCredentialTypes
)
from .threat_intelligence import (
    ThreatIntelligenceEngine,
    ThreatIndicator,
    ThreatReport,
    ThreatType,
    ThreatSeverity,
    IndicatorType,
    BloomFilter
)
from .auto_isolation import (
    AutoIsolationManager,
    IsolationLevel,
    IsolationReason,
    IsolationRecord,
    CircuitBreaker,
    QuarantineZone
)
from .policy_engine import (
    PolicyEngine,
    PolicyEnforcer,
    Policy,
    PolicyRule,
    PolicyCondition,
    PolicyDecision,
    PolicyEffect,
    AttributeType
)
from .continuous_verification import (
    ContinuousVerificationEngine,
    Session,
    VerificationCheck,
    VerificationResult,
    VerificationType,
    RiskLevel,
    BehaviorProfile
)

__all__ = [
    # Core
    "ZeroTrustValidator",
    
    # ZKP Authentication
    "SchnorrZKP",
    "PedersenCommitment", 
    "ZKPAuthenticator",
    "ZKPChallenge",
    "ZKPProof",
    
    # Device Attestation
    "DeviceAttestor",
    "AdaptiveTrustManager",
    "MeshDeviceAttestor",
    "TrustLevel",
    "TrustScore",
    "AttestationType",
    
    # Post-Quantum
    "SimplifiedNTRU",
    "HybridEncryption",
    "QuantumSafeKeyExchange",
    "PQMeshSecurity",
    "PQAlgorithm",
    
    # Decentralized Identity (NEW)
    "DIDManager",
    "DIDResolver",
    "DIDDocument",
    "VerifiableCredential",
    "DIDMethod",
    "MeshCredentialTypes",
    
    # Threat Intelligence (NEW)
    "ThreatIntelligenceEngine",
    "ThreatIndicator",
    "ThreatReport",
    "ThreatType",
    "ThreatSeverity",
    "IndicatorType",
    "BloomFilter",
    
    # Auto-Isolation (NEW)
    "AutoIsolationManager",
    "IsolationLevel",
    "IsolationReason",
    "IsolationRecord",
    "CircuitBreaker",
    "QuarantineZone",
    
    # Policy Engine (NEW)
    "PolicyEngine",
    "PolicyEnforcer",
    "Policy",
    "PolicyRule",
    "PolicyCondition",
    "PolicyDecision",
    "PolicyEffect",
    "AttributeType",
    
    # Continuous Verification (NEW)
    "ContinuousVerificationEngine",
    "Session",
    "VerificationCheck",
    "VerificationResult",
    "VerificationType",
    "RiskLevel",
    "BehaviorProfile"
]

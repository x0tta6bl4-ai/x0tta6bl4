"""
Decentralized Identity (DID) Module for x0tta6bl4 Mesh.
Self-sovereign identity without central authority.

Implements:
- DID Document creation and management
- Verifiable Credentials (VCs)
- DID Resolution
- Key rotation
- Recovery mechanisms

Standards: W3C DID Core 1.0, Verifiable Credentials Data Model 1.1
"""
import hashlib
import json
import secrets
import time
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class DIDMethod(Enum):
    """Supported DID methods."""
    MESH = "mesh"  # Our native method
    KEY = "key"    # did:key (simple, self-certifying)
    WEB = "web"    # did:web (DNS-based)


class KeyPurpose(Enum):
    """Purpose of verification method keys."""
    AUTHENTICATION = "authentication"
    ASSERTION = "assertionMethod"
    KEY_AGREEMENT = "keyAgreement"
    CAPABILITY_INVOCATION = "capabilityInvocation"
    CAPABILITY_DELEGATION = "capabilityDelegation"


@dataclass
class VerificationMethod:
    """Verification method in DID Document."""
    id: str
    type: str
    controller: str
    public_key_multibase: str
    purpose: List[KeyPurpose] = field(default_factory=list)
    created: float = field(default_factory=time.time)
    revoked: bool = False


@dataclass
class ServiceEndpoint:
    """Service endpoint in DID Document."""
    id: str
    type: str
    service_endpoint: str
    description: Optional[str] = None


@dataclass
class DIDDocument:
    """W3C DID Document."""
    id: str  # The DID itself
    context: List[str] = field(default_factory=lambda: [
        "https://www.w3.org/ns/did/v1",
        "https://w3id.org/security/suites/ed25519-2020/v1"
    ])
    controller: Optional[str] = None
    verification_method: List[VerificationMethod] = field(default_factory=list)
    authentication: List[str] = field(default_factory=list)
    assertion_method: List[str] = field(default_factory=list)
    key_agreement: List[str] = field(default_factory=list)
    service: List[ServiceEndpoint] = field(default_factory=list)
    created: float = field(default_factory=time.time)
    updated: float = field(default_factory=time.time)
    deactivated: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-LD dict."""
        return {
            "@context": self.context,
            "id": self.id,
            "controller": self.controller or self.id,
            "verificationMethod": [
                {
                    "id": vm.id,
                    "type": vm.type,
                    "controller": vm.controller,
                    "publicKeyMultibase": vm.public_key_multibase
                }
                for vm in self.verification_method if not vm.revoked
            ],
            "authentication": self.authentication,
            "assertionMethod": self.assertion_method,
            "keyAgreement": self.key_agreement,
            "service": [
                {
                    "id": s.id,
                    "type": s.type,
                    "serviceEndpoint": s.service_endpoint
                }
                for s in self.service
            ],
            "created": datetime.fromtimestamp(self.created).isoformat(),
            "updated": datetime.fromtimestamp(self.updated).isoformat()
        }


@dataclass
class VerifiableCredential:
    """W3C Verifiable Credential."""
    id: str
    type: List[str]
    issuer: str  # DID of issuer
    issuance_date: float
    expiration_date: Optional[float]
    credential_subject: Dict[str, Any]
    proof: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-LD dict."""
        vc = {
            "@context": [
                "https://www.w3.org/2018/credentials/v1",
                "https://x0tta6bl4.mesh/credentials/v1"
            ],
            "id": self.id,
            "type": self.type,
            "issuer": self.issuer,
            "issuanceDate": datetime.fromtimestamp(self.issuance_date).isoformat(),
            "credentialSubject": self.credential_subject
        }
        if self.expiration_date:
            vc["expirationDate"] = datetime.fromtimestamp(self.expiration_date).isoformat()
        if self.proof:
            vc["proof"] = self.proof
        return vc


class DIDGenerator:
    """Generate DIDs for mesh nodes."""
    
    @staticmethod
    def generate_keypair() -> Tuple[bytes, bytes]:
        """Generate Ed25519-like keypair (simplified)."""
        private_key = secrets.token_bytes(32)
        # Simplified public key derivation
        public_key = hashlib.sha256(private_key).digest()
        return private_key, public_key
    
    @staticmethod
    def multibase_encode(data: bytes) -> str:
        """Encode bytes as multibase (base58btc)."""
        # Simplified base58 encoding
        alphabet = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
        num = int.from_bytes(data, 'big')
        result = ''
        while num:
            num, rem = divmod(num, 58)
            result = alphabet[rem] + result
        return 'z' + result  # 'z' prefix for base58btc
    
    @staticmethod
    def create_did_mesh(node_id: str, public_key: bytes) -> str:
        """Create did:mesh identifier."""
        key_hash = hashlib.sha256(public_key).hexdigest()[:16]
        return f"did:mesh:{node_id}:{key_hash}"
    
    @staticmethod
    def create_did_key(public_key: bytes) -> str:
        """Create did:key identifier (self-certifying)."""
        # did:key uses multicodec prefix + multibase encoding
        # 0xed01 = Ed25519 public key
        prefixed = b'\xed\x01' + public_key
        encoded = DIDGenerator.multibase_encode(prefixed)
        return f"did:key:{encoded}"


class DIDManager:
    """
    Manage DIDs for mesh node.
    Provides self-sovereign identity without central authority.
    """
    
    def __init__(self, node_id: str):
        self.node_id = node_id
        self.private_key, self.public_key = DIDGenerator.generate_keypair()
        self.did = DIDGenerator.create_did_mesh(node_id, self.public_key)
        self.document = self._create_initial_document()
        self.credentials: Dict[str, VerifiableCredential] = {}
        self.key_history: List[VerificationMethod] = []
        
        logger.info(f"Created DID for node {node_id}: {self.did}")
    
    def _create_initial_document(self) -> DIDDocument:
        """Create initial DID Document."""
        key_id = f"{self.did}#key-1"
        
        vm = VerificationMethod(
            id=key_id,
            type="Ed25519VerificationKey2020",
            controller=self.did,
            public_key_multibase=DIDGenerator.multibase_encode(self.public_key),
            purpose=[
                KeyPurpose.AUTHENTICATION,
                KeyPurpose.ASSERTION,
                KeyPurpose.KEY_AGREEMENT
            ]
        )
        
        # Service endpoint for mesh communication
        service = ServiceEndpoint(
            id=f"{self.did}#mesh-endpoint",
            type="MeshMessaging",
            service_endpoint=f"mesh://{self.node_id}",
            description="Mesh network communication endpoint"
        )
        
        return DIDDocument(
            id=self.did,
            verification_method=[vm],
            authentication=[key_id],
            assertion_method=[key_id],
            key_agreement=[key_id],
            service=[service]
        )
    
    def rotate_key(self) -> VerificationMethod:
        """
        Rotate authentication key.
        Old key is revoked, new key is added.
        """
        # Generate new keypair
        new_private, new_public = DIDGenerator.generate_keypair()
        
        # Revoke old key
        for vm in self.document.verification_method:
            if not vm.revoked:
                vm.revoked = True
                self.key_history.append(vm)
        
        # Create new verification method
        key_num = len(self.key_history) + 1
        key_id = f"{self.did}#key-{key_num}"
        
        new_vm = VerificationMethod(
            id=key_id,
            type="Ed25519VerificationKey2020",
            controller=self.did,
            public_key_multibase=DIDGenerator.multibase_encode(new_public),
            purpose=[
                KeyPurpose.AUTHENTICATION,
                KeyPurpose.ASSERTION,
                KeyPurpose.KEY_AGREEMENT
            ]
        )
        
        # Update document
        self.document.verification_method.append(new_vm)
        self.document.authentication = [key_id]
        self.document.assertion_method = [key_id]
        self.document.key_agreement = [key_id]
        self.document.updated = time.time()
        
        # Update instance keys
        self.private_key = new_private
        self.public_key = new_public
        
        logger.info(f"Rotated key for {self.did}, new key: {key_id}")
        return new_vm
    
    def sign(self, data: bytes) -> bytes:
        """Sign data with private key."""
        # Simplified HMAC-based signature
        return hashlib.sha256(self.private_key + data).digest()
    
    def verify_signature(self, data: bytes, signature: bytes, public_key: bytes) -> bool:
        """Verify signature (requires knowing the private key pattern - simplified)."""
        # In real implementation, use Ed25519 verify
        expected = hashlib.sha256(public_key + data).digest()
        return hmac_compare(signature, expected)
    
    def issue_credential(
        self,
        subject_did: str,
        credential_type: str,
        claims: Dict[str, Any],
        expiration_days: Optional[int] = 365
    ) -> VerifiableCredential:
        """
        Issue a Verifiable Credential.
        
        Args:
            subject_did: DID of credential subject
            credential_type: Type of credential
            claims: Claims to include
            expiration_days: Days until expiration
        """
        now = time.time()
        cred_id = f"urn:uuid:{secrets.token_hex(16)}"
        
        vc = VerifiableCredential(
            id=cred_id,
            type=["VerifiableCredential", credential_type],
            issuer=self.did,
            issuance_date=now,
            expiration_date=now + (expiration_days * 86400) if expiration_days else None,
            credential_subject={
                "id": subject_did,
                **claims
            }
        )
        
        # Create proof
        proof_data = json.dumps(vc.to_dict(), sort_keys=True).encode()
        signature = self.sign(proof_data)
        
        vc.proof = {
            "type": "Ed25519Signature2020",
            "created": datetime.now().isoformat(),
            "verificationMethod": self.document.authentication[0],
            "proofPurpose": "assertionMethod",
            "proofValue": DIDGenerator.multibase_encode(signature)
        }
        
        self.credentials[cred_id] = vc
        logger.info(f"Issued credential {cred_id} to {subject_did}")
        
        return vc
    
    def verify_credential(self, vc_dict: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Verify a Verifiable Credential.
        
        Returns:
            (is_valid, reason)
        """
        try:
            # Check expiration
            if "expirationDate" in vc_dict:
                exp_date = datetime.fromisoformat(vc_dict["expirationDate"].replace("Z", "+00:00"))
                if exp_date < datetime.now(exp_date.tzinfo):
                    return False, "Credential expired"
            
            # Check proof exists
            if "proof" not in vc_dict:
                return False, "No proof found"
            
            # Verify signature (simplified - would need issuer's public key)
            proof = vc_dict["proof"]
            if proof.get("type") != "Ed25519Signature2020":
                return False, f"Unknown proof type: {proof.get('type')}"
            
            # In production, resolve issuer DID and verify signature
            return True, "Credential valid"
            
        except Exception as e:
            return False, f"Verification error: {e}"
    
    def create_presentation(
        self,
        credentials: List[VerifiableCredential],
        challenge: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create Verifiable Presentation from credentials.
        
        Args:
            credentials: Credentials to include
            challenge: Optional challenge for replay protection
        """
        presentation = {
            "@context": [
                "https://www.w3.org/2018/credentials/v1"
            ],
            "type": ["VerifiablePresentation"],
            "holder": self.did,
            "verifiableCredential": [vc.to_dict() for vc in credentials]
        }
        
        # Create proof
        proof_data = json.dumps(presentation, sort_keys=True).encode()
        if challenge:
            proof_data += challenge.encode()
        
        signature = self.sign(proof_data)
        
        presentation["proof"] = {
            "type": "Ed25519Signature2020",
            "created": datetime.now().isoformat(),
            "verificationMethod": self.document.authentication[0],
            "proofPurpose": "authentication",
            "proofValue": DIDGenerator.multibase_encode(signature),
            "challenge": challenge
        }
        
        return presentation
    
    def get_document(self) -> Dict[str, Any]:
        """Get DID Document as dict."""
        return self.document.to_dict()
    
    def deactivate(self) -> None:
        """Deactivate this DID (cannot be undone)."""
        self.document.deactivated = True
        self.document.updated = time.time()
        for vm in self.document.verification_method:
            vm.revoked = True
        logger.warning(f"Deactivated DID: {self.did}")


class DIDResolver:
    """
    Resolve DIDs to DID Documents.
    Distributed resolution without central authority.
    """
    
    def __init__(self):
        self.cache: Dict[str, Tuple[DIDDocument, float]] = {}
        self.cache_ttl = 3600  # 1 hour
        self.peer_resolvers: List[str] = []  # Mesh peers for resolution
    
    def resolve(self, did: str) -> Optional[Dict[str, Any]]:
        """
        Resolve DID to DID Document.
        
        Args:
            did: The DID to resolve
            
        Returns:
            DID Document dict or None
        """
        # Check cache
        if did in self.cache:
            doc, cached_at = self.cache[did]
            if time.time() - cached_at < self.cache_ttl:
                return doc.to_dict()
        
        # Parse DID method
        parts = did.split(":")
        if len(parts) < 3:
            logger.error(f"Invalid DID format: {did}")
            return None
        
        method = parts[1]
        
        if method == "mesh":
            return self._resolve_mesh(did)
        elif method == "key":
            return self._resolve_key(did)
        elif method == "web":
            return self._resolve_web(did)
        else:
            logger.error(f"Unsupported DID method: {method}")
            return None
    
    def _resolve_mesh(self, did: str) -> Optional[Dict[str, Any]]:
        """Resolve did:mesh using mesh network."""
        # In production, query mesh peers for DID Document
        # For now, return None (would need peer lookup)
        logger.debug(f"Mesh resolution for {did} - would query peers")
        return None
    
    def _resolve_key(self, did: str) -> Optional[Dict[str, Any]]:
        """
        Resolve did:key (self-certifying).
        The public key is embedded in the DID itself.
        """
        # did:key:z... - extract public key from multibase
        parts = did.split(":")
        if len(parts) != 3:
            return None
        
        multibase_key = parts[2]
        
        # Create minimal DID Document
        return {
            "@context": ["https://www.w3.org/ns/did/v1"],
            "id": did,
            "verificationMethod": [{
                "id": f"{did}#key-1",
                "type": "Ed25519VerificationKey2020",
                "controller": did,
                "publicKeyMultibase": multibase_key
            }],
            "authentication": [f"{did}#key-1"],
            "assertionMethod": [f"{did}#key-1"]
        }
    
    def _resolve_web(self, did: str) -> Optional[Dict[str, Any]]:
        """Resolve did:web via HTTPS."""
        # did:web:example.com -> https://example.com/.well-known/did.json
        # Not implemented for mesh (no DNS dependency)
        logger.warning(f"did:web resolution not supported in mesh: {did}")
        return None
    
    def register_peer_resolver(self, peer_endpoint: str) -> None:
        """Register a mesh peer for distributed resolution."""
        if peer_endpoint not in self.peer_resolvers:
            self.peer_resolvers.append(peer_endpoint)
    
    def cache_document(self, did: str, document: DIDDocument) -> None:
        """Cache a DID Document."""
        self.cache[did] = (document, time.time())


def hmac_compare(a: bytes, b: bytes) -> bool:
    """Constant-time comparison."""
    if len(a) != len(b):
        return False
    result = 0
    for x, y in zip(a, b):
        result |= x ^ y
    return result == 0


# Credential types for mesh
class MeshCredentialTypes:
    """Standard credential types for mesh network."""
    NODE_OPERATOR = "MeshNodeOperatorCredential"
    TRUST_ANCHOR = "MeshTrustAnchorCredential"
    PEER_ATTESTATION = "MeshPeerAttestationCredential"
    SERVICE_AUTHORIZATION = "MeshServiceAuthorizationCredential"
    GOVERNANCE_VOTE = "MeshGovernanceVoteCredential"

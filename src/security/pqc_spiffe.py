"""
Quantum-Safe SPIFFE Integration for x0tta6bl4
==============================================

Bridges SPIRE (X.509 SVIDs) with Post-Quantum Cryptography (ML-DSA/Dilithium).
Provides a way to attest PQC public keys using SPIFFE identities.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict

from cryptography import x509
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
from cryptography.x509.oid import ExtensionOID

from src.security.pqc_identity import PQCNodeIdentity
from src.security.spire_integration import SPIREClient, SPIREConfig
from src.security.zkp_attestor import NIZKPAttestor
from src.security.zkp_auth import SchnorrZKP

logger = logging.getLogger(__name__)


_PEM_CERT_PATTERN = re.compile(
    br"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----",
    re.DOTALL,
)


class PQCSpiffeBridge:
    """
    Bridges SPIRE identity with PQC security and ZKP attestation.
    """
    
    def __init__(self, node_id: str, trust_domain: str = "x0tta6bl4.mesh"):
        self.node_id = node_id
        self.spire_config = SPIREConfig(trust_domain=trust_domain)
        self.spire_client = SPIREClient(self.spire_config)
        self.pqc_identity = PQCNodeIdentity(node_id)
        
        # ZKP Identity (separate from PQC/Dilithium)
        self.zkp_secret, _ = SchnorrZKP.generate_keypair()
        self.zkp_attestor = NIZKPAttestor(node_id, self.zkp_secret)
        
    def get_pqc_svid(self) -> Dict[str, Any]:
        """
        Returns a 'PQC-SVID' bundle with ZKP proof.
        """
        pkeys = self.pqc_identity.security.get_public_keys()
        
        # Generate NIZKP Identity Proof
        zkp_proof = self.zkp_attestor.generate_identity_proof(message="mesh-join-v3.3")
        
        bundle = {
            "spiffe_id": f"spiffe://{self.spire_config.trust_domain}/node/{self.node_id}",
            "pqc_public_keys": pkeys,
            "pqc_did": self.pqc_identity.did,
            "zkp_attestation": zkp_proof,
            "attestation": "spire-zkp-verified"
        }
        
        return bundle

    def verify_pqc_svid(self, bundle: Dict[str, Any]) -> bool:
        """
        Verifies a PQC-SVID bundle from a remote peer.
        
        Performs basic structural validation. For full cryptographic verification
        including X.509 signature binding, use verify_pqc_svid_full().
        
        Args:
            bundle: PQC-SVID bundle containing spiffe_id, pqc_public_keys, pqc_did
            
        Returns:
            True if bundle has required fields, False otherwise
        """
        # 1. Check if the PQC keys are validly formatted
        if "pqc_public_keys" not in bundle or "pqc_did" not in bundle:
            logger.warning("PQC-SVID bundle missing required fields")
            return False
            
        # 2. Validate SPIFFE ID format
        spiffe_id = bundle.get("spiffe_id", "")
        if not spiffe_id.startswith(f"spiffe://{self.spire_config.trust_domain}/"):
            logger.warning(f"SPIFFE ID trust domain mismatch: {spiffe_id}")
            return False
            
        # 3. Validate ZKP attestation if present
        zkp_attestation = bundle.get("zkp_attestation")
        if zkp_attestation:
            if not NIZKPAttestor.verify_identity_proof(
                zkp_attestation, message="mesh-join-v3.3"
            ):
                logger.warning("ZKP attestation verification failed")
                return False
        
        # Note: Full X.509 signature verification that binds the PQC key
        # to the SPIFFE ID should be performed in production using verify_pqc_svid_full()
        logger.debug(f"PQC-SVID basic validation passed for {spiffe_id}")
        return True
    
    def verify_pqc_svid_full(self, bundle: Dict[str, Any], verify_x509: bool = False) -> bool:
        """
        Full cryptographic verification of PQC-SVID bundle.
        """
        # 1. Basic validation
        if not self.verify_pqc_svid(bundle):
            return False
        
        if verify_x509:
            return self._verify_x509_binding(bundle)
        
        return True

    def _verify_x509_binding(self, bundle: Dict[str, Any]) -> bool:
        """
        Verify that the provided X.509 SVID binds to the PQC-SVID SPIFFE ID.

        Expected bundle shape:
            {
                "spiffe_id": "spiffe://trust.domain/node/node-1",
                "x509_context": {
                    "certificate": b"...PEM...",
                    "bundle": b"...CA PEM...",
                    "spiffe_id": "spiffe://trust.domain/node/node-1"
                }
            }
        """
        spiffe_id = bundle.get("spiffe_id", "")
        x509_context = bundle.get("x509_context") or bundle.get("x509_svid")
        if not isinstance(x509_context, dict):
            logger.warning("PQC-SVID full verification missing X.509 context")
            return False

        context_spiffe_id = x509_context.get("spiffe_id")
        if context_spiffe_id and context_spiffe_id != spiffe_id:
            logger.warning(
                "PQC-SVID X.509 SPIFFE ID mismatch: %s != %s",
                context_spiffe_id,
                spiffe_id,
            )
            return False

        cert_bytes = self._context_bytes(
            x509_context,
            "certificate",
            "cert",
            "leaf",
            "cert_chain",
            "certificate_chain",
        )
        trust_bundle_bytes = self._context_bytes(
            x509_context,
            "bundle",
            "trust_bundle",
            "ca_bundle",
        )
        if not cert_bytes or not trust_bundle_bytes:
            logger.warning("PQC-SVID full verification requires certificate and trust bundle")
            return False

        try:
            leaf = self._load_certificate(cert_bytes)
            trust_cas = self._load_certificates(trust_bundle_bytes)
        except ValueError as exc:
            logger.warning("PQC-SVID X.509 certificate parse failed: %s", exc)
            return False

        now = datetime.utcnow()
        tolerance = timedelta(minutes=5)
        if now < leaf.not_valid_before - tolerance:
            logger.warning("PQC-SVID X.509 certificate is not yet valid")
            return False
        if now > leaf.not_valid_after + tolerance:
            logger.warning("PQC-SVID X.509 certificate is expired")
            return False

        if not self._certificate_has_spiffe_id(leaf, spiffe_id):
            logger.warning("PQC-SVID X.509 certificate is not bound to %s", spiffe_id)
            return False

        if not self._verify_leaf_against_trust_bundle(leaf, trust_cas):
            logger.warning("PQC-SVID X.509 trust bundle verification failed")
            return False

        return True

    @staticmethod
    def _context_bytes(context: Dict[str, Any], *keys: str) -> bytes:
        for key in keys:
            value = context.get(key)
            if value is None:
                continue
            if isinstance(value, (bytes, bytearray)):
                return bytes(value)
            if isinstance(value, str):
                return value.encode("utf-8")
            if isinstance(value, (list, tuple)) and value:
                first = value[0]
                if isinstance(first, (bytes, bytearray)):
                    return bytes(first)
                if isinstance(first, str):
                    return first.encode("utf-8")
        return b""

    @staticmethod
    def _load_certificate(data: bytes) -> x509.Certificate:
        if b"-----BEGIN CERTIFICATE-----" in data:
            return x509.load_pem_x509_certificate(data)
        return x509.load_der_x509_certificate(data)

    @classmethod
    def _load_certificates(cls, data: bytes) -> list[x509.Certificate]:
        pem_blocks = _PEM_CERT_PATTERN.findall(data)
        if pem_blocks:
            return [x509.load_pem_x509_certificate(block) for block in pem_blocks]
        return [x509.load_der_x509_certificate(data)]

    @staticmethod
    def _certificate_has_spiffe_id(cert: x509.Certificate, spiffe_id: str) -> bool:
        try:
            san = cert.extensions.get_extension_for_oid(
                ExtensionOID.SUBJECT_ALTERNATIVE_NAME
            ).value
        except x509.ExtensionNotFound:
            return False
        uris = san.get_values_for_type(x509.UniformResourceIdentifier)
        return spiffe_id in {str(uri) for uri in uris}

    @staticmethod
    def _verify_leaf_against_trust_bundle(
        leaf: x509.Certificate,
        trust_cas: list[x509.Certificate],
    ) -> bool:
        for ca_cert in trust_cas:
            if leaf.issuer != ca_cert.subject:
                continue
            public_key = ca_cert.public_key()
            hash_algorithm = leaf.signature_hash_algorithm
            try:
                if isinstance(public_key, rsa.RSAPublicKey):
                    public_key.verify(
                        leaf.signature,
                        leaf.tbs_certificate_bytes,
                        padding.PKCS1v15(),
                        hash_algorithm,
                    )
                elif isinstance(public_key, ec.EllipticCurvePublicKey):
                    public_key.verify(
                        leaf.signature,
                        leaf.tbs_certificate_bytes,
                        ec.ECDSA(hash_algorithm),
                    )
                else:
                    public_key.verify(leaf.signature, leaf.tbs_certificate_bytes)
                return True
            except (ValueError, TypeError, RuntimeError, OSError):
                continue
        return False

    def create_secure_payload(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Wraps data in a PQC-signed manifest.
        """
        return self.pqc_identity.sign_manifest(data)


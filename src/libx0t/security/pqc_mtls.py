"""
Post-Quantum mTLS Integration

Integrates ML-KEM-768 and ML-DSA-65 with mTLS for quantum-resistant
secure communication.
"""
from __future__ import annotations

import logging
import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from src.core.thinking.agent_thinking import AgentThinkingCoach

from .pqc_core import PQCKeyPair, PQCSignature, get_pqc_hybrid

logger = logging.getLogger(__name__)


def _safe_hash(value: object) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]


def _safe_count_bucket(value: int) -> str:
    if value <= 0:
        return "0"
    if value <= 3:
        return "1-3"
    if value <= 10:
        return "4-10"
    if value <= 100:
        return "11-100"
    return "100+"


def _safe_number_band(value: object) -> str:
    if not isinstance(value, (int, float)):
        return "non_numeric"
    if value < 0:
        return "negative"
    if value == 0:
        return "0"
    if value <= 30:
        return "1-30"
    if value <= 365:
        return "31-365"
    return "365+"


@dataclass
class PQCCertificate:
    """PQC-enhanced certificate"""

    certificate_pem: bytes
    private_key_pem: bytes
    pqc_public_key: bytes
    pqc_signature: Optional[PQCSignature] = None
    created_at: datetime = None
    expires_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.expires_at is None:
            self.expires_at = self.created_at + timedelta(days=365)


class PQCmTLSController:
    """Post-Quantum mTLS Controller"""

    def __init__(self, enable_hybrid: bool = True):
        """
        Initialize PQC mTLS controller.

        Args:
            enable_hybrid: Enable hybrid classical+PQC mode
        """
        self.enable_hybrid = enable_hybrid
        self.pqc_hybrid = get_pqc_hybrid() if enable_hybrid else None
        self.certificates: Dict[str, PQCCertificate] = {}
        self.pqc_keys: Dict[str, PQCKeyPair] = {}
        self.enabled = self.pqc_hybrid is not None and self.pqc_hybrid.enable_pqc
        self.thinking_coach = AgentThinkingCoach(
            agent_id=f"pqc-mtls-controller:{_safe_hash(enable_hybrid)}",
            role="security",
            capabilities=("zero-trust", "ops"),
        )
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": "pqc_mtls_controller_init",
                "goal": "Initialize PQC mTLS controller safely",
                "signals": {
                    "hybrid_mode": enable_hybrid,
                    "enabled": self.enabled,
                    "key_count_bucket": "0",
                    "certificate_count_bucket": "0",
                },
                "safety_boundary": (
                    "Keep raw request data, response data, signatures, private keys, "
                    "public keys, common names, certificate PEM, and key IDs out of "
                    "thinking context."
                ),
            }
        )

        logger.info(f"PQC mTLS: {'enabled' if self.enabled else 'disabled'}")

    def _record_thinking(
        self,
        task_type: str,
        goal: str,
        signals: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": task_type,
                "goal": goal,
                "signals": signals or {},
                "constraints": {
                    "redact_request_data": True,
                    "redact_response_data": True,
                    "redact_signatures": True,
                    "redact_private_keys": True,
                    "redact_public_keys": True,
                    "redact_common_names": True,
                    "redact_certificates": True,
                    "redact_key_ids": True,
                    "preserve_pqc_channel_decision": True,
                },
                "safety_boundary": "Use hashes, counts, booleans, algorithms, statuses, and size bands.",
            }
        )
        return self.last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        return {
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
        }

    def initialize_pqc_keys(self, validity_days: int = 365) -> Dict[str, Any]:
        """
        Initialize PQC keypairs for mTLS.

        Args:
            validity_days: Key validity period

        Returns:
            Initialization status
        """
        if not self.enabled:
            self._record_thinking(
                "pqc_mtls_keys_init_skipped",
                "Skip PQC mTLS key initialization when disabled",
                {"enabled": False, "validity_days_band": _safe_number_band(validity_days)},
            )
            return {"status": "disabled", "reason": "PQC not available"}

        try:
            # Generate ML-KEM-768 keypair (key exchange)
            kem_keypair = self.pqc_hybrid.kem.generate_keypair(
                key_id="mtls_kem", validity_days=validity_days
            )
            self.pqc_keys["kem"] = kem_keypair

            # Generate ML-DSA-65 keypair (signatures)
            dsa_keypair = self.pqc_hybrid.dsa.generate_keypair(
                key_id="mtls_dsa", validity_days=validity_days
            )
            self.pqc_keys["dsa"] = dsa_keypair

            logger.info("Initialized PQC keypairs for mTLS")

            result = {
                "status": "success",
                "kem_key_id": kem_keypair.key_id,
                "dsa_key_id": dsa_keypair.key_id,
                "expires_at": kem_keypair.expires_at.isoformat(),
                "algorithms": ["ML-KEM-768", "ML-DSA-65"],
            }
            self._record_thinking(
                "pqc_mtls_keys_initialized",
                "Initialize PQC mTLS keypairs safely",
                {
                    "enabled": True,
                    "validity_days_band": _safe_number_band(validity_days),
                    "kem_key_hash": _safe_hash(kem_keypair.key_id),
                    "dsa_key_hash": _safe_hash(dsa_keypair.key_id),
                    "key_count_bucket": _safe_count_bucket(len(self.pqc_keys)),
                    "algorithms": result["algorithms"],
                },
            )
            return result

        except Exception as e:
            logger.error(f"Failed to initialize PQC keys: {e}")
            self._record_thinking(
                "pqc_mtls_keys_init_failed",
                "Record PQC mTLS key initialization failure safely",
                {"enabled": self.enabled, "error_type": type(e).__name__},
            )
            return {"status": "error", "error": str(e)}

    def establish_pqc_channel(self) -> Dict[str, Any]:
        """
        Establish PQC-protected communication channel.

        Returns:
            Channel establishment status
        """
        if not self.enabled:
            self._record_thinking(
                "pqc_mtls_channel_disabled",
                "Use classical TLS when PQC mTLS is disabled",
                {"enabled": False, "method": "classical_tls_1_3"},
            )
            return {"status": "disabled", "method": "classical_tls_1_3"}

        try:
            setup = self.pqc_hybrid.setup_secure_channel()
            result = {
                "status": "success",
                "method": "hybrid_pqc_tls",
                "key_exchange": "ML-KEM-768",
                "signature": "ML-DSA-65",
                "shared_secret_bits": setup.get("shared_secret_len", 0) * 8,
                "timestamp": datetime.utcnow().isoformat(),
            }
            self._record_thinking(
                "pqc_mtls_channel_established",
                "Establish PQC-protected channel safely",
                {
                    "enabled": True,
                    "method": result["method"],
                    "key_exchange": result["key_exchange"],
                    "signature": result["signature"],
                    "shared_secret_bits_band": _safe_number_band(
                        result["shared_secret_bits"]
                    ),
                },
            )
            return result

        except Exception as e:
            logger.error(f"Failed to establish PQC channel: {e}")
            self._record_thinking(
                "pqc_mtls_channel_failed",
                "Record PQC channel establishment failure safely",
                {"enabled": self.enabled, "error_type": type(e).__name__},
            )
            return {"status": "error", "fallback": "tls_1_3", "error": str(e)}

    def sign_request(self, request_data: bytes) -> Tuple[bytes, PQCSignature]:
        """
        Sign mTLS request with PQC.

        Args:
            request_data: Request data to sign

        Returns:
            (signed_data, signature)
        """
        if not self.enabled or "dsa" not in self.pqc_keys:
            self._record_thinking(
                "pqc_mtls_sign_blocked",
                "Block PQC signing without DSA key safely",
                {
                    "enabled": self.enabled,
                    "has_dsa_key": "dsa" in self.pqc_keys,
                    "request_data_length_band": _safe_number_band(len(request_data)),
                },
            )
            raise RuntimeError("PQC signature not available")

        dsa_keypair = self.pqc_keys["dsa"]
        signature = self.pqc_hybrid.dsa.sign(
            request_data, dsa_keypair.secret_key, dsa_keypair.key_id
        )

        self._record_thinking(
            "pqc_mtls_request_signed",
            "Sign mTLS request with PQC safely",
            {
                "request_data_hash": _safe_hash(request_data),
                "request_data_length_band": _safe_number_band(len(request_data)),
                "dsa_key_hash": _safe_hash(dsa_keypair.key_id),
                "signature_type": type(signature).__name__,
            },
        )
        return request_data, signature

    def verify_response(
        self, response_data: bytes, signature_bytes: bytes
    ) -> bool:
        """
        Verify PQC-signed response.

        Args:
            response_data: Response data
            signature_bytes: PQC signature

        Returns:
            Verification result
        """
        if not self.enabled or "dsa" not in self.pqc_keys:
            self._record_thinking(
                "pqc_mtls_response_verify_blocked",
                "Block PQC response verification without DSA key safely",
                {
                    "enabled": self.enabled,
                    "has_dsa_key": "dsa" in self.pqc_keys,
                    "response_data_length_band": _safe_number_band(len(response_data)),
                    "signature_length_band": _safe_number_band(len(signature_bytes)),
                },
            )
            return False

        dsa_keypair = self.pqc_keys["dsa"]

        verified = self.pqc_hybrid.dsa.verify(
            response_data, signature_bytes, dsa_keypair.public_key
        )
        self._record_thinking(
            "pqc_mtls_response_verified",
            "Verify PQC-signed response safely",
            {
                "response_data_hash": _safe_hash(response_data),
                "response_data_length_band": _safe_number_band(len(response_data)),
                "signature_hash": _safe_hash(signature_bytes),
                "signature_length_band": _safe_number_band(len(signature_bytes)),
                "dsa_key_hash": _safe_hash(dsa_keypair.key_id),
                "verified": verified,
            },
        )
        return verified

    def _generate_classical_cert_bundle(
        self, common_name: str, validity_days: int
    ) -> Tuple[bytes, bytes]:
        """Generate a minimal classical cert/key pair for hybrid mTLS metadata."""
        private_key = rsa.generate_private_key(
            public_exponent=65537, key_size=2048, backend=default_backend()
        )
        subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
        now = datetime.utcnow()
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(subject)
            .public_key(private_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=1))
            .not_valid_after(now + timedelta(days=validity_days))
            .add_extension(
                x509.BasicConstraints(ca=False, path_length=None),
                critical=True,
            )
            .sign(private_key=private_key, algorithm=hashes.SHA256())
        )

        certificate_pem = cert.public_bytes(encoding=serialization.Encoding.PEM)
        private_key_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        return certificate_pem, private_key_pem

    def create_pqc_certificate(
        self, common_name: str, validity_days: int = 365
    ) -> PQCCertificate:
        """
        Create PQC-enhanced certificate.

        Args:
            common_name: Certificate common name
            validity_days: Certificate validity period

        Returns:
            PQCCertificate
        """
        if not self.enabled:
            self._record_thinking(
                "pqc_certificate_create_blocked",
                "Block PQC certificate creation when disabled",
                {
                    "enabled": False,
                    "common_name_hash": _safe_hash(common_name),
                    "validity_days_band": _safe_number_band(validity_days),
                },
            )
            raise RuntimeError("PQC not available")

        try:
            cert_data = f"CN={common_name}".encode()
            certificate_pem, private_key_pem = self._generate_classical_cert_bundle(
                common_name=common_name,
                validity_days=validity_days,
            )

            # Sign with ML-DSA-65
            signature = self.pqc_hybrid.dsa.sign(
                cert_data, self.pqc_keys["dsa"].secret_key, self.pqc_keys["dsa"].key_id
            )

            pqc_cert = PQCCertificate(
                certificate_pem=certificate_pem,
                private_key_pem=private_key_pem,
                pqc_public_key=self.pqc_keys["dsa"].public_key,
                pqc_signature=signature,
                created_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(days=validity_days),
            )

            cert_id = f"{common_name}_{datetime.utcnow().timestamp()}"
            self.certificates[cert_id] = pqc_cert

            logger.info(f"Created PQC certificate: {cert_id}")

            self._record_thinking(
                "pqc_certificate_created",
                "Create PQC-enhanced certificate safely",
                {
                    "common_name_hash": _safe_hash(common_name),
                    "certificate_id_hash": _safe_hash(cert_id),
                    "validity_days_band": _safe_number_band(validity_days),
                    "certificate_count_bucket": _safe_count_bucket(
                        len(self.certificates)
                    ),
                    "pqc_public_key_length_band": _safe_number_band(
                        len(pqc_cert.pqc_public_key)
                    ),
                    "has_signature": pqc_cert.pqc_signature is not None,
                },
            )
            return pqc_cert

        except Exception as e:
            logger.error(f"Failed to create PQC certificate: {e}")
            self._record_thinking(
                "pqc_certificate_create_failed",
                "Record PQC certificate creation failure safely",
                {
                    "common_name_hash": _safe_hash(common_name),
                    "error_type": type(e).__name__,
                },
            )
            raise

    def rotate_pqc_keys(self, validity_days: int = 365) -> Dict[str, Any]:
        """
        Rotate PQC keys for post-quantum readiness.

        Args:
            validity_days: New key validity period

        Returns:
            Rotation status
        """
        if not self.enabled:
            self._record_thinking(
                "pqc_mtls_key_rotation_skipped",
                "Skip PQC mTLS key rotation when disabled",
                {"enabled": False, "validity_days_band": _safe_number_band(validity_days)},
            )
            return {"status": "disabled"}

        try:
            old_kem_id = (
                self.pqc_keys.get("kem", {}).key_id if "kem" in self.pqc_keys else None
            )
            old_dsa_id = (
                self.pqc_keys.get("dsa", {}).key_id if "dsa" in self.pqc_keys else None
            )

            # Generate new keys
            kem_keypair = self.pqc_hybrid.kem.generate_keypair(
                key_id=f"mtls_kem_rotated_{datetime.utcnow().timestamp()}",
                validity_days=validity_days,
            )
            dsa_keypair = self.pqc_hybrid.dsa.generate_keypair(
                key_id=f"mtls_dsa_rotated_{datetime.utcnow().timestamp()}",
                validity_days=validity_days,
            )

            # Update keys
            self.pqc_keys["kem"] = kem_keypair
            self.pqc_keys["dsa"] = dsa_keypair

            logger.info(
                f"Rotated PQC keys: KEM {old_kem_id} -> {kem_keypair.key_id}, "
                f"DSA {old_dsa_id} -> {dsa_keypair.key_id}"
            )

            result = {
                "status": "success",
                "old_kem_key_id": old_kem_id,
                "new_kem_key_id": kem_keypair.key_id,
                "old_dsa_key_id": old_dsa_id,
                "new_dsa_key_id": dsa_keypair.key_id,
                "rotated_at": datetime.utcnow().isoformat(),
            }
            self._record_thinking(
                "pqc_mtls_keys_rotated",
                "Rotate PQC mTLS keys safely",
                {
                    "old_kem_key_hash": _safe_hash(old_kem_id),
                    "new_kem_key_hash": _safe_hash(kem_keypair.key_id),
                    "old_dsa_key_hash": _safe_hash(old_dsa_id),
                    "new_dsa_key_hash": _safe_hash(dsa_keypair.key_id),
                    "validity_days_band": _safe_number_band(validity_days),
                    "key_count_bucket": _safe_count_bucket(len(self.pqc_keys)),
                },
            )
            return result

        except Exception as e:
            logger.error(f"Failed to rotate PQC keys: {e}")
            self._record_thinking(
                "pqc_mtls_key_rotation_failed",
                "Record PQC mTLS key rotation failure safely",
                {"enabled": self.enabled, "error_type": type(e).__name__},
            )
            return {"status": "error", "error": str(e)}

    def get_status(self) -> Dict[str, Any]:
        """Get current PQC mTLS status."""
        status = {
            "enabled": self.enabled,
            "hybrid_mode": self.enable_hybrid,
            "algorithms": ["ML-KEM-768", "ML-DSA-65"] if self.enabled else [],
            "keys_initialized": bool(self.pqc_keys),
            "certificates_issued": len(self.certificates),
            "fallback": "TLS 1.3 classical" if not self.enabled else "none",
            "timestamp": datetime.utcnow().isoformat(),
        }
        self._record_thinking(
            "pqc_mtls_status_reported",
            "Report PQC mTLS status safely",
            {
                "enabled": self.enabled,
                "hybrid_mode": self.enable_hybrid,
                "key_count_bucket": _safe_count_bucket(len(self.pqc_keys)),
                "certificate_count_bucket": _safe_count_bucket(
                    len(self.certificates)
                ),
                "fallback": status["fallback"],
            },
        )
        return status


# Global instance
_pqc_mtls_controller: Optional[PQCmTLSController] = None


def get_pqc_mtls_controller(enable_hybrid: bool = True) -> PQCmTLSController:
    """Get or create PQC mTLS controller."""
    global _pqc_mtls_controller
    if _pqc_mtls_controller is None:
        _pqc_mtls_controller = PQCmTLSController(enable_hybrid=enable_hybrid)
    return _pqc_mtls_controller


def test_pqc_mtls_setup() -> Dict[str, Any]:
    """Test PQC mTLS setup."""
    controller = get_pqc_mtls_controller()

    # Initialize keys
    key_init = controller.initialize_pqc_keys()

    # Establish channel
    channel = controller.establish_pqc_channel()

    status = "success"
    if key_init.get("status") in {"disabled", "error"}:
        status = key_init.get("status", "error")

    return {
        "status": status,
        "mtls_controller_status": controller.get_status(),
        "key_initialization": key_init,
        "channel_establishment": channel,
        "overall_status": "success" if key_init["status"] == "success" else "partial",
    }


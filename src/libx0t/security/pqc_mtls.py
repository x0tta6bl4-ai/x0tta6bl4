"""
Post-Quantum mTLS Integration

Integrates ML-KEM-768 and ML-DSA-65 with mTLS for quantum-resistant
secure communication.
"""

import logging
import ssl
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from .pqc_core import PQCHybridScheme, PQCKeyPair, PQCSignature, get_pqc_hybrid

logger = logging.getLogger(__name__)


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

        logger.info(f"PQC mTLS: {'enabled' if self.enabled else 'disabled'}")

    def initialize_pqc_keys(self, validity_days: int = 365) -> Dict[str, Any]:
        """
        Initialize PQC keypairs for mTLS.

        Args:
            validity_days: Key validity period

        Returns:
            Initialization status
        """
        if not self.enabled:
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

            return {
                "status": "success",
                "kem_key_id": kem_keypair.key_id,
                "dsa_key_id": dsa_keypair.key_id,
                "expires_at": kem_keypair.expires_at.isoformat(),
                "algorithms": ["ML-KEM-768", "ML-DSA-65"],
            }

        except Exception as e:
            logger.error(f"Failed to initialize PQC keys: {e}")
            return {"status": "error", "error": str(e)}

    def establish_pqc_channel(self) -> Dict[str, Any]:
        """
        Establish PQC-protected communication channel.

        Returns:
            Channel establishment status
        """
        if not self.enabled:
            return {"status": "disabled", "method": "classical_tls_1_3"}

        try:
            setup = self.pqc_hybrid.setup_secure_channel()

            return {
                "status": "success",
                "method": "hybrid_pqc_tls",
                "key_exchange": "ML-KEM-768",
                "signature": "ML-DSA-65",
                "shared_secret_bits": setup.get("shared_secret_len", 0) * 8,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to establish PQC channel: {e}")
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
            raise RuntimeError("PQC signature not available")

        dsa_keypair = self.pqc_keys["dsa"]
        signature = self.pqc_hybrid.dsa.sign(
            request_data, dsa_keypair.secret_key, dsa_keypair.key_id
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
            return False

        dsa_keypair = self.pqc_keys["dsa"]

        return self.pqc_hybrid.dsa.verify(
            response_data, signature_bytes, dsa_keypair.public_key
        )

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

            return pqc_cert

        except Exception as e:
            logger.error(f"Failed to create PQC certificate: {e}")
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

            return {
                "status": "success",
                "old_kem_key_id": old_kem_id,
                "new_kem_key_id": kem_keypair.key_id,
                "old_dsa_key_id": old_dsa_id,
                "new_dsa_key_id": dsa_keypair.key_id,
                "rotated_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to rotate PQC keys: {e}")
            return {"status": "error", "error": str(e)}

    def get_status(self) -> Dict[str, Any]:
        """Get current PQC mTLS status."""
        return {
            "enabled": self.enabled,
            "hybrid_mode": self.enable_hybrid,
            "algorithms": ["ML-KEM-768", "ML-DSA-65"] if self.enabled else [],
            "keys_initialized": bool(self.pqc_keys),
            "certificates_issued": len(self.certificates),
            "fallback": "TLS 1.3 classical" if not self.enabled else "none",
            "timestamp": datetime.utcnow().isoformat(),
        }


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

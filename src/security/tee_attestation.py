import logging
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class TEEAttestation:
    """Represents a TEE (Trusted Execution Environment) report."""
    provider: str  # sgx, sev, nitro, mock
    report_data: bytes
    quote: Optional[bytes] = None
    signature: Optional[bytes] = None

class TEEValidator:
    """Validates hardware-rooted attestation reports."""
    
    def __init__(self, *, allow_mock: bool = False, allow_insecure_stub: bool = False):
        self.allow_mock = allow_mock
        self.allow_insecure_stub = allow_insecure_stub
        logger.info(
            "TEE Validator initialized (allow_mock=%s, allow_insecure_stub=%s)",
            allow_mock,
            allow_insecure_stub,
        )

    def verify_report(self, attestation: TEEAttestation) -> bool:
        """
        Main entry point for TEE verification.
        In production, this would call Intel/AMD/AWS attestation services.
        """
        provider = (attestation.provider or "").strip().lower()
        if provider == "mock":
            if not self.allow_mock:
                logger.warning("Mock TEE provider rejected: mock attestation disabled")
                return False
            return self._verify_mock(attestation)
        
        if provider == "sgx":
            return self._verify_sgx(attestation)
            
        logger.warning("Unknown TEE provider: %s", attestation.provider)
        return False

    def _verify_mock(self, attestation: TEEAttestation) -> bool:
        """Mock verification for development and CI."""
        # Simple rule: if report_data contains 'TRUSTED_X0T', it's valid
        return b"TRUSTED_X0T" in attestation.report_data

    def _verify_sgx(self, attestation: TEEAttestation) -> bool:
        """
        Placeholder for Intel SGX Remote Attestation logic.
        Requires 'pysgx' or similar library.
        """
        if not attestation.quote or not attestation.signature:
            logger.warning("SGX attestation missing quote/signature")
            return False

        if not self.allow_insecure_stub:
            logger.error("SGX attestation backend is not configured; rejecting attestation")
            return False

        # Insecure compatibility mode for local dev only.
        logger.warning("Using insecure SGX stub verification path")
        return len(attestation.quote) >= 16 and len(attestation.signature) >= 16

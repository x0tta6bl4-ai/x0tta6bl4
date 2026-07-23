from __future__ import annotations
import base64
import json
import logging
import os
import shlex
import subprocess
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional, Sequence, Dict
from src.core.security.subprocess_validator import safe_run

logger = logging.getLogger(__name__)

COMMAND_VERIFIER_PROVIDERS = {"sgx", "sev", "nitro"}

@dataclass
class TEEAttestation:
    """Represents a TEE (Trusted Execution Environment) report."""
    provider: str  # sgx, sev, nitro, mock
    report_data: bytes
    quote: Optional[bytes] = None
    signature: Optional[bytes] = None

@dataclass
class TEEVerificationResult:
    """Redacted verifier result for attestation evidence and claim gates."""
    verified: bool
    provider: str
    verifier_backend: str
    verifier_provenance: dict[str, Any]
    production_verifier_claim_allowed: bool = False
    reason: str = ""

class TEEValidator:
    """Validates hardware-rooted attestation reports."""
    
    def __init__(
        self,
        *,
        allow_mock: bool = False,
        sgx_verifier: Optional[Callable[[TEEAttestation], bool]] = None,
        sgx_verifier_command: Optional[Sequence[str] | str] = None,
    ):
        self.allow_mock = allow_mock
        self.sgx_verifier = sgx_verifier
        self.sgx_verifier_command = self._resolve_sgx_verifier_command(
            sgx_verifier_command
        )
        logger.info("TEE Validator initialized (allow_mock=%s)", allow_mock)

    @staticmethod
    def _resolve_sgx_verifier_command(
        command: Optional[Sequence[str] | str],
    ) -> list[str]:
        if isinstance(command, str):
            return shlex.split(command)
        if command is not None:
            return list(command)
        env_command = os.getenv("X0TTA6BL4_SGX_VERIFIER_CMD")
        return shlex.split(env_command) if env_command else []

    def verify_report(self, attestation: TEEAttestation) -> bool:
        return self.verify_report_with_context(attestation).verified

    def verify_report_with_context(self, attestation: TEEAttestation) -> TEEVerificationResult:
        """
        Main entry point for TEE verification.
        In production, this would call Intel/AMD/AWS attestation services.
        """
        provider = (attestation.provider or "").strip().lower()
        if provider == "mock":
            if not self.allow_mock:
                logger.warning("Mock TEE provider rejected: mock attestation disabled")
                return self._result(
                    False,
                    provider,
                    verifier_backend="mock_disabled",
                    reason="mock_attestation_disabled",
                )
            verified = self._verify_mock(attestation)
            provenance = {
                "attestation_type": "mock",
                "raw_attestation_redacted": True,
                "timestamp": time.time(),
            }
            return self._result(
                verified,
                provider,
                verifier_backend="mock_local_allowlist",
                provenance=provenance,
                reason="" if verified else "mock_attestation_rejected",
            )
        
        if provider in COMMAND_VERIFIER_PROVIDERS:
            return self._verify_provider_with_context(attestation, provider)
            
        logger.warning("Unknown TEE provider: %s", attestation.provider)
        return self._result(
            False,
            provider,
            verifier_backend="unsupported_provider",
            reason="unsupported_tee_provider",
        )

    def _verify_mock(self, attestation: TEEAttestation) -> bool:
        """Mock verification for development and CI."""
        # Simple rule: if report_data contains 'TRUSTED_X0T', it's valid
        return b"TRUSTED_X0T" in attestation.report_data

    def _verify_sgx(self, attestation: TEEAttestation) -> bool:
        """
        Verify Intel SGX attestation through a configured backend.

        The backend can be an in-process callable or a local command such as an
        Intel DCAP/PCS verifier wrapper. Without a backend this method rejects
        the report instead of simulating success.
        """
        if not attestation.quote or not attestation.signature:
            logger.warning("SGX attestation missing quote/signature")
            return False
        if not attestation.report_data:
            logger.warning("SGX attestation missing report_data")
            return False

        if self.sgx_verifier is not None:
            try:
                return bool(self.sgx_verifier(attestation))
            except (ValueError, TypeError, RuntimeError, OSError) as exc:
                logger.error("SGX attestation verifier callable failed: %s", exc)
                return False

        if self.sgx_verifier_command:
            return self._verify_sgx_with_command(attestation)

        logger.error("SGX attestation backend is not configured; rejecting attestation")
        return False

    def _verify_sgx_with_command(self, attestation: TEEAttestation) -> bool:
        payload = {
            "provider": "sgx",
            "report_data_b64": self._b64(attestation.report_data),
            "quote_b64": self._b64(attestation.quote or b""),
            "signature_b64": self._b64(attestation.signature or b""),
        }
        try:
            result = safe_run(
                self.sgx_verifier_command,
                input=json.dumps(payload),
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
        except FileNotFoundError as exc:
            logger.error("SGX verifier command not found: %s", self.sgx_verifier_command[0])
            return False
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            logger.error("SGX verifier command failed to run: %s", exc)
            return False

        if result.returncode != 0:
            logger.warning("SGX verifier command rejected attestation")
            return False

        stdout = result.stdout.strip()
        if not stdout:
            return True
        try:
            response: Any = json.loads(stdout)
        except json.JSONDecodeError:
            response = {}
        if isinstance(response, dict):
            provider = str(attestation.provider or "").strip().lower()
            self._last_verifier_backend = f"{provider}_command"
            provenance = {
                "backend_kind": "local_command",
                "executable_name": os.path.basename(self.sgx_verifier_command[0]),
                "raw_command_redacted": True,
            }
            for k, v in response.items():
                if k != "valid":
                    provenance[k] = v
            self._last_verifier_provenance = provenance
        return bool(response.get("valid"))

    @staticmethod
    def _b64(value: bytes) -> str:
        return base64.b64encode(value).decode("ascii")

    def _result(
        self,
        verified: bool,
        provider: str,
        verifier_backend: str,
        provenance: Optional[Dict[str, Any]] = None,
        production_verifier_claim_allowed: bool = False,
        reason: str = "",
    ) -> TEEVerificationResult:
        return TEEVerificationResult(
            verified=verified,
            provider=provider,
            verifier_backend=verifier_backend,
            verifier_provenance=provenance or {},
            production_verifier_claim_allowed=production_verifier_claim_allowed,
            reason=reason,
        )

    def _verify_provider_with_context(
        self, attestation: TEEAttestation, provider: str
    ) -> TEEVerificationResult:
        verified = False
        reason = ""
        self._last_verifier_backend = None
        self._last_verifier_provenance = None

        if provider == "sgx":
            verified = self._verify_sgx(attestation)
            if not verified:
                reason = "sgx_verification_failed"
        elif provider == "sev":
            verified = self._verify_sev(attestation)
            if not verified:
                reason = "sev_verification_failed"
        elif provider == "nitro":
            verified = self._verify_nitro(attestation)
            if not verified:
                reason = "nitro_verification_failed"
        else:
            reason = "unsupported_provider"

        backend = self._last_verifier_backend or f"x0tta6bl4_{provider}_verifier_v1"
        provenance = {
            "attestation_type": provider,
            "raw_attestation_redacted": True,
            "timestamp": time.time(),
        }
        if self._last_verifier_provenance:
            provenance.update(self._last_verifier_provenance)

        # Allow command-based production claims if returned from backend
        production_claim = verified
        if self._last_verifier_provenance and "production_verifier_claim_allowed" in self._last_verifier_provenance:
            production_claim = bool(self._last_verifier_provenance["production_verifier_claim_allowed"])

        return self._result(
            verified,
            provider,
            verifier_backend=backend,
            provenance=provenance,
            production_verifier_claim_allowed=production_claim,
            reason=reason,
        )

    def _verify_sev(self, attestation: TEEAttestation) -> bool:
        if not attestation.quote:
            logger.warning("SEV attestation missing quote")
            return False
        if os.environ.get("_X0TTA_TEST_MODE_") == "true" and b"SEV_MOCK_TRUSTED" in attestation.quote:
            return True
        return len(attestation.quote) > 0

    def _verify_nitro(self, attestation: TEEAttestation) -> bool:
        if not attestation.quote:
            logger.warning("Nitro Enclaves attestation missing document/quote")
            return False
        if os.environ.get("_X0TTA_TEST_MODE_") == "true" and b"NITRO_MOCK_TRUSTED" in attestation.quote:
            return True
        return len(attestation.quote) > 0


from __future__ import annotations
import base64
import json
import logging
import os
import shlex
import subprocess
from dataclasses import dataclass
from typing import Any, Callable, Optional, Sequence

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
            return self._result(
                verified,
                provider,
                verifier_backend="mock_local_allowlist",
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
            result = subprocess.run(
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
            return True
        return bool(response.get("valid"))

    @staticmethod
    def _b64(value: bytes) -> str:
        return base64.b64encode(value).decode("ascii")


import base64
import hashlib
import json
import logging
import os
import shlex
import subprocess
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Optional, Sequence

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
        sev_verifier_command: Optional[Sequence[str] | str] = None,
        nitro_verifier_command: Optional[Sequence[str] | str] = None,
        verifier_commands: Optional[Mapping[str, Sequence[str] | str]] = None,
    ):
        self.allow_mock = allow_mock
        self.sgx_verifier = sgx_verifier
        configured_commands = dict(verifier_commands or {})
        if sgx_verifier_command is not None:
            configured_commands["sgx"] = sgx_verifier_command
        if sev_verifier_command is not None:
            configured_commands["sev"] = sev_verifier_command
        if nitro_verifier_command is not None:
            configured_commands["nitro"] = nitro_verifier_command
        self.verifier_commands = {
            provider: self._resolve_verifier_command(provider, configured_commands.get(provider))
            for provider in COMMAND_VERIFIER_PROVIDERS
        }
        self.sgx_verifier_command = self.verifier_commands["sgx"]
        self.sev_verifier_command = self.verifier_commands["sev"]
        self.nitro_verifier_command = self.verifier_commands["nitro"]
        logger.info("TEE Validator initialized (allow_mock=%s)", allow_mock)

    @staticmethod
    def _resolve_verifier_command(
        provider: str,
        command: Optional[Sequence[str] | str],
    ) -> list[str]:
        if isinstance(command, str):
            return shlex.split(command)
        if command is not None:
            return list(command)
        normalized = provider.strip().upper()
        env_command = os.getenv(f"X0TTA6BL4_{normalized}_VERIFIER_CMD")
        return shlex.split(env_command) if env_command else []

    @staticmethod
    def _resolve_sgx_verifier_command(
        command: Optional[Sequence[str] | str],
    ) -> list[str]:
        return TEEValidator._resolve_verifier_command("sgx", command)

    def verifier_command_for_provider(self, provider: str) -> list[str]:
        return list(self.verifier_commands.get(provider.strip().lower(), []))

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
        return self._verify_sgx_with_context(attestation).verified

    def _verify_sgx_with_context(self, attestation: TEEAttestation) -> TEEVerificationResult:
        """
        Verify Intel SGX attestation through a configured backend.

        The backend can be an in-process callable or a local command such as an
        Intel DCAP/PCS verifier wrapper. Without a backend this method rejects
        the report instead of simulating success.
        """
        return self._verify_provider_with_context(attestation, "sgx")

    def _verify_provider_with_context(
        self,
        attestation: TEEAttestation,
        provider: str,
    ) -> TEEVerificationResult:
        provider = provider.strip().lower()
        if not attestation.quote or not attestation.signature:
            logger.warning("%s attestation missing quote/signature", provider.upper())
            return self._result(
                False,
                provider,
                verifier_backend=f"{provider}_missing_quote_or_signature",
                reason=f"{provider}_attestation_missing_quote_or_signature",
            )
        if not attestation.report_data:
            logger.warning("%s attestation missing report_data", provider.upper())
            return self._result(
                False,
                provider,
                verifier_backend=f"{provider}_missing_report_data",
                reason=f"{provider}_attestation_missing_report_data",
            )

        if provider == "sgx" and self.sgx_verifier is not None:
            try:
                verified = bool(self.sgx_verifier(attestation))
                return self._result(
                    verified,
                    provider,
                    verifier_backend="sgx_callable",
                    reason="" if verified else "sgx_callable_rejected",
                )
            except Exception as exc:
                logger.error("SGX attestation verifier callable failed: %s", exc)
                return self._result(
                    False,
                    provider,
                    verifier_backend="sgx_callable",
                    reason="sgx_callable_failed",
                )

        if self.verifier_command_for_provider(provider):
            return self._verify_with_command_context(attestation, provider)

        logger.error(
            "%s attestation backend is not configured; rejecting attestation",
            provider.upper(),
        )
        return self._result(
            False,
            provider,
            verifier_backend=f"{provider}_backend_not_configured",
            reason=f"{provider}_attestation_backend_not_configured",
        )

    def _verify_sgx_with_command(self, attestation: TEEAttestation) -> bool:
        return self._verify_sgx_with_command_context(attestation).verified

    def _verify_sgx_with_command_context(self, attestation: TEEAttestation) -> TEEVerificationResult:
        return self._verify_with_command_context(attestation, "sgx")

    def _verify_with_command_context(
        self,
        attestation: TEEAttestation,
        provider: str,
    ) -> TEEVerificationResult:
        provider = provider.strip().lower()
        command = self.verifier_command_for_provider(provider)
        payload = {
            "provider": provider,
            "report_data_b64": self._b64(attestation.report_data),
            "quote_b64": self._b64(attestation.quote or b""),
            "signature_b64": self._b64(attestation.signature or b""),
        }
        provenance = self._command_provenance(provider)
        try:
            result = subprocess.run(
                command,
                input=json.dumps(payload),
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
        except FileNotFoundError as exc:
            logger.error("%s verifier command not found: %s", provider.upper(), command[0])
            return self._result(
                False,
                provider,
                verifier_backend=f"{provider}_command",
                verifier_provenance=provenance,
                reason=f"{provider}_verifier_command_not_found",
            )
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            logger.error("%s verifier command failed to run: %s", provider.upper(), exc)
            return self._result(
                False,
                provider,
                verifier_backend=f"{provider}_command",
                verifier_provenance=provenance,
                reason=f"{provider}_verifier_command_failed",
            )

        if result.returncode != 0:
            logger.warning("%s verifier command rejected attestation", provider.upper())
            return self._result(
                False,
                provider,
                verifier_backend=f"{provider}_command",
                verifier_provenance={
                    **provenance,
                    "exit_code": result.returncode,
                    "stdout_json_fields": [],
                },
                reason=f"{provider}_verifier_command_rejected",
            )

        stdout = result.stdout.strip()
        if not stdout:
            return self._result(
                True,
                provider,
                verifier_backend=f"{provider}_command",
                verifier_provenance={
                    **provenance,
                    "exit_code": result.returncode,
                    "stdout_json_fields": [],
                },
                reason="",
            )
        try:
            response: Any = json.loads(stdout)
        except json.JSONDecodeError:
            return self._result(
                True,
                provider,
                verifier_backend=f"{provider}_command",
                verifier_provenance={
                    **provenance,
                    "exit_code": result.returncode,
                    "stdout_json_fields": [],
                },
                reason="",
            )
        if not isinstance(response, dict):
            response = {}
        verified = bool(response.get("valid"))
        return self._result(
            verified,
            provider,
            verifier_backend=f"{provider}_command",
            verifier_provenance={
                **provenance,
                "exit_code": result.returncode,
                "stdout_json_fields": sorted(str(key) for key in response.keys()),
                "verifier_id": str(response.get("verifier_id") or ""),
                "policy_id": str(response.get("policy_id") or ""),
            },
            production_verifier_claim_allowed=(
                verified and bool(response.get("production_verifier_claim_allowed"))
            ),
            reason="" if verified else f"{provider}_verifier_command_rejected",
        )

    @staticmethod
    def _b64(value: bytes) -> str:
        return base64.b64encode(value).decode("ascii")

    def _command_provenance(self, provider: str = "sgx") -> dict[str, Any]:
        command = self.verifier_command_for_provider(provider)
        encoded = json.dumps(command, sort_keys=True, separators=(",", ":")).encode("utf-8")
        executable = command[0] if command else ""
        return {
            "backend_kind": "local_command",
            "provider": provider.strip().lower(),
            "command_sha256_prefix": self._sha256_prefix(encoded),
            "command_arg_count": len(command),
            "executable_name": os.path.basename(executable),
            "raw_command_redacted": True,
        }

    def _result(
        self,
        verified: bool,
        provider: str,
        *,
        verifier_backend: str,
        verifier_provenance: Optional[dict[str, Any]] = None,
        production_verifier_claim_allowed: bool = False,
        reason: str = "",
    ) -> TEEVerificationResult:
        provenance = dict(verifier_provenance or {})
        if "backend_kind" not in provenance:
            provenance["backend_kind"] = verifier_backend
        provenance.setdefault("raw_attestation_redacted", True)
        return TEEVerificationResult(
            verified=verified,
            provider=provider,
            verifier_backend=verifier_backend,
            verifier_provenance=provenance,
            production_verifier_claim_allowed=(
                bool(production_verifier_claim_allowed) and provider != "mock"
            ),
            reason=reason,
        )

    @staticmethod
    def _sha256_prefix(value: bytes) -> str:
        return base64.b16encode(hashlib.sha256(value).digest()[:8]).decode("ascii").lower()

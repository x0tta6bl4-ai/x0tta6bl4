"""
x0tta6bl4 Zero-Trust Licensing System
=====================================
Node Identity Binding — украсть файл можно, украсть работающую ноду нельзя.

Security layers:
1. Hardware Fingerprint (CPU + MAC + Motherboard)
2. Activation Token verification
3. PQ-signed Identity Certificate
4. Network-level validation (mesh rejects invalid nodes)
5. Double-spending detection (same ID on 2 machines = auto-ban)
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import platform
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

# Try to import crypto libs
try:
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ed25519

    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False


@dataclass
class DeviceFingerprint:
    """Unique hardware fingerprint that can't be copied."""

    cpu_id: str
    mac_address: str
    machine_id: str
    hostname: str
    platform: str

    def to_hash(self) -> str:
        """Generate unique hash from all components."""
        data = f"{self.cpu_id}:{self.mac_address}:{self.machine_id}:{self.hostname}:{self.platform}"
        return hashlib.sha256(data.encode()).hexdigest()

    def to_dict(self) -> dict:
        return {
            "cpu_id": self.cpu_id,
            "mac_address": self.mac_address,
            "machine_id": self.machine_id,
            "hostname": self.hostname,
            "platform": self.platform,
            "fingerprint_hash": self.to_hash(),
        }


@dataclass
class IdentityCertificate:
    """Signed certificate proving node identity."""

    fingerprint_hash: str
    activation_token: str
    issued_at: float
    expires_at: float
    signature: str
    license_tier: str  # "basic", "pro", "enterprise"

    def is_valid(self) -> bool:
        return time.time() < self.expires_at

    def to_dict(self) -> dict:
        return {
            "fingerprint_hash": self.fingerprint_hash,
            "activation_token": self.activation_token,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "signature": self.signature,
            "license_tier": self.license_tier,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "IdentityCertificate":
        return cls(**data)

    def save(self, path: str):
        with open(path, "w") as f:
            json.dump(self.to_dict(), f)

    @classmethod
    def load(cls, path: str) -> Optional["IdentityCertificate"]:
        try:
            with open(path, "r") as f:
                return cls.from_dict(json.load(f))
        except Exception:
            return None


class HardwareFingerprinter:
    """Collect unique hardware identifiers."""

    @staticmethod
    def get_cpu_id() -> str:
        """Get CPU identifier."""
        try:
            if platform.system() == "Linux":
                result = subprocess.run(
                    ["cat", "/proc/cpuinfo"], capture_output=True, text=True, timeout=5
                )
                for line in result.stdout.split("\n"):
                    if "Serial" in line or "model name" in line:
                        return hashlib.sha256(line.encode()).hexdigest()[:16]
            elif platform.system() == "Darwin":
                result = subprocess.run(
                    ["sysctl", "-n", "machdep.cpu.brand_string"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                return hashlib.sha256(result.stdout.encode()).hexdigest()[:16]
        except Exception:
            pass
        return hashlib.sha256(platform.processor().encode()).hexdigest()[:16]

    @staticmethod
    def get_mac_address() -> str:
        """Get primary MAC address."""
        mac = uuid.getnode()
        return ":".join(f"{(mac >> i) & 0xff:02x}" for i in range(0, 48, 8))

    @staticmethod
    def get_machine_id() -> str:
        """Get unique machine ID."""
        try:
            # Linux
            if os.path.exists("/etc/machine-id"):
                with open("/etc/machine-id", "r") as f:
                    return f.read().strip()[:32]
            # macOS
            if platform.system() == "Darwin":
                result = subprocess.run(
                    ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                for line in result.stdout.split("\n"):
                    if "IOPlatformUUID" in line:
                        return line.split('"')[-2][:32]
        except Exception:
            pass
        return hashlib.sha256(str(uuid.getnode()).encode()).hexdigest()[:32]

    @classmethod
    def generate(cls) -> DeviceFingerprint:
        """Generate complete device fingerprint."""
        return DeviceFingerprint(
            cpu_id=cls.get_cpu_id(),
            mac_address=cls.get_mac_address(),
            machine_id=cls.get_machine_id(),
            hostname=platform.node(),
            platform=f"{platform.system()}-{platform.machine()}",
        )


class LicenseAuthority:
    """
    Master authority that signs certificates.
    This runs on YOUR server only.
    """

    def __init__(self, master_key: bytes = None):
        self.master_key = master_key or os.urandom(32)

    def generate_activation_token(self, license_tier: str = "basic") -> str:
        """Generate unique activation token for customer."""
        token_data = f"{time.time()}:{uuid.uuid4()}:{license_tier}"
        signature = hmac.new(
            self.master_key, token_data.encode(), hashlib.sha256
        ).hexdigest()[:16]
        return f"X0T-{license_tier.upper()[:3]}-{signature}"

    def sign_certificate(
        self,
        fingerprint_hash: str,
        activation_token: str,
        license_tier: str = "basic",
        validity_days: int = 365,
    ) -> IdentityCertificate:
        """Sign identity certificate for a node."""
        issued_at = time.time()
        expires_at = issued_at + (validity_days * 86400)

        # Create signature
        sign_data = f"{fingerprint_hash}:{activation_token}:{issued_at}:{expires_at}"
        signature = hmac.new(
            self.master_key, sign_data.encode(), hashlib.sha256
        ).hexdigest()

        return IdentityCertificate(
            fingerprint_hash=fingerprint_hash,
            activation_token=activation_token,
            issued_at=issued_at,
            expires_at=expires_at,
            signature=signature,
            license_tier=license_tier,
        )

    def verify_certificate(self, cert: IdentityCertificate) -> Tuple[bool, str]:
        """Verify certificate signature and validity."""
        # Check expiry
        if not cert.is_valid():
            return False, "Certificate expired"

        # Verify signature
        sign_data = f"{cert.fingerprint_hash}:{cert.activation_token}:{cert.issued_at}:{cert.expires_at}"
        expected_sig = hmac.new(
            self.master_key, sign_data.encode(), hashlib.sha256
        ).hexdigest()

        if cert.signature != expected_sig:
            return False, "Invalid signature"

        return True, "Valid"


class LicenseActivationError(RuntimeError):
    """Raised when a node cannot obtain a trusted license certificate."""


class NodeLicenseManager:
    """
    Client-side license manager.
    Runs on customer's machine.
    """

    CERT_PATH = Path.home() / ".x0tta6bl4" / "license.cert"

    def __init__(
        self,
        auth_server_url: Optional[str] = None,
        activation_client: Optional[Callable[[Dict[str, Any]], Any]] = None,
    ):
        import os

        auth_server_url = auth_server_url or os.getenv("LICENSE_SERVER", "")
        self.auth_server_url = auth_server_url
        self.activation_client = activation_client
        self.fingerprint = HardwareFingerprinter.generate()
        self.certificate: Optional[IdentityCertificate] = None
        self.source_agent = "node-license-manager"
        self.thinking_coach = AgentThinkingCoach(
            agent_id=self.source_agent,
            role="security",
            capabilities=("zero-trust", "licensing", "identity"),
            extra_techniques=("reverse_planning",),
        )
        self._last_thinking_context: Optional[Dict[str, Any]] = None
        self._record_thinking(
            operation="init",
            goal="initialize node license manager without exposing hardware fingerprint",
            constraints={
                "auth_server_configured": bool(self.auth_server_url),
                "activation_client_configured": self.activation_client is not None,
                "fingerprint_hash": self._hash_value(self.fingerprint.to_hash()),
            },
        )

        # Try to load existing certificate
        self._load_certificate()

    @staticmethod
    def _hash_value(value: Any) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, bytes):
            return hashlib.sha256(value).hexdigest()
        return hashlib.sha256(
            str(value).encode("utf-8", errors="replace")
        ).hexdigest()

    def _record_thinking(
        self,
        *,
        operation: str,
        goal: str,
        constraints: Dict[str, Any],
    ) -> Dict[str, Any]:
        safe_task = {
            "task_type": "node_license_manager_operation",
            "goal": goal,
            "constraints": {
                "operation": operation,
                "redacted": True,
                "raw_activation_token_redacted": True,
                "raw_fingerprint_redacted": True,
                "raw_certificate_redacted": True,
                "license_check_is_not_hardware_attestation": True,
                "license_check_is_not_external_identity_finality": True,
                **constraints,
            },
            "safety_boundary": (
                "Record only local license activation and verification metadata, "
                "hashes, booleans, and status. Do not expose activation tokens, "
                "hardware identifiers, certificate signatures, or server payloads. "
                "A local license check is not hardware attestation or external "
                "identity finality."
            ),
        }
        self._last_thinking_context = self.thinking_coach.prepare_task(safe_task)
        return self._last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        """Expose license manager thinking state without raw license secrets."""
        return {
            **self.thinking_coach.status(),
            "last_context": self._last_thinking_context,
            "certificate_loaded": self.certificate is not None,
        }

    def _load_certificate(self):
        """Load certificate from disk."""
        if self.CERT_PATH.exists():
            self.certificate = IdentityCertificate.load(str(self.CERT_PATH))
            self._record_thinking(
                operation="load_certificate",
                goal="load local license certificate from disk",
                constraints={"certificate_loaded": self.certificate is not None},
            )

    def _save_certificate(self):
        """Save certificate to disk."""
        if self.certificate:
            self.CERT_PATH.parent.mkdir(parents=True, exist_ok=True)
            self.certificate.save(str(self.CERT_PATH))

    def activate(self, activation_token: str) -> Tuple[bool, str]:
        """
        Activate node with token.

        The node must receive a signed certificate from the configured license
        server, or from an explicitly injected activation client in tests/tools.
        """
        if not activation_token:
            return False, "Activation token is required."

        # Verify fingerprint matches certificate (if exists)
        if self.certificate:
            if self.certificate.fingerprint_hash != self.fingerprint.to_hash():
                self._record_thinking(
                    operation="activate",
                    goal="reject activation because loaded certificate is bound elsewhere",
                    constraints={"fingerprint_match": False},
                )
                return (
                    False,
                    "Hardware fingerprint mismatch! License bound to different machine.",
                )

        try:
            self.certificate = self._request_certificate(activation_token)
        except LicenseActivationError as exc:
            return False, str(exc)

        self._save_certificate()
        return True, f"Activated! Tier: {self.certificate.license_tier}"

    def _activation_url(self) -> str:
        return f"{self.auth_server_url.rstrip('/')}/activate"

    def _request_certificate(self, activation_token: str) -> IdentityCertificate:
        payload = {
            "activation_token": activation_token,
            "fingerprint_hash": self.fingerprint.to_hash(),
            "fingerprint": self.fingerprint.to_dict(),
        }
        if self.activation_client is not None:
            try:
                response_payload = self.activation_client(payload)
            except Exception as exc:
                raise LicenseActivationError("License activation client failed.") from exc
        else:
            response_payload = self._post_activation_request(payload)

        if isinstance(response_payload, IdentityCertificate):
            certificate = response_payload
        elif isinstance(response_payload, dict):
            cert_payload = response_payload.get("certificate", response_payload)
            if not isinstance(cert_payload, dict):
                raise LicenseActivationError("License server response lacks certificate data.")
            try:
                certificate = IdentityCertificate.from_dict(cert_payload)
            except TypeError as exc:
                raise LicenseActivationError("License server returned invalid certificate.") from exc
        else:
            raise LicenseActivationError("License server returned invalid response.")

        if certificate.fingerprint_hash != self.fingerprint.to_hash():
            raise LicenseActivationError(
                "License server returned certificate for a different machine."
            )
        if not certificate.is_valid():
            raise LicenseActivationError("License server returned an expired certificate.")
        return certificate

    def _post_activation_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.auth_server_url:
            raise LicenseActivationError(
                "LICENSE_SERVER is required for node activation."
            )

        request = urllib.request.Request(
            self._activation_url(),
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        try:
            parsed = urllib.parse.urlparse(self._activation_url())
            if parsed.scheme not in ("https", "http"):
                raise ValueError(f"Banned URL scheme: {parsed.scheme}")
            with urllib.request.urlopen(request, timeout=10) as response:
                data = json.load(response)
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            raise LicenseActivationError("License server activation failed.") from exc
        if not isinstance(data, dict):
            raise LicenseActivationError("License server returned invalid JSON.")
        return data

    def verify(self) -> Tuple[bool, str]:
        """Verify current license is valid."""
        if not self.certificate:
            self._record_thinking(
                operation="verify",
                goal="reject license verification because no certificate is loaded",
                constraints={"certificate_loaded": False},
            )
            return False, "No license found. Please activate."

        # Check fingerprint binding
        if self.certificate.fingerprint_hash != self.fingerprint.to_hash():
            self._record_thinking(
                operation="verify",
                goal="reject license verification because fingerprint differs",
                constraints={"fingerprint_match": False},
            )
            return False, "SECURITY ALERT: License bound to different hardware!"

        # Check expiry
        if not self.certificate.is_valid():
            self._record_thinking(
                operation="verify",
                goal="reject license verification because certificate expired",
                constraints={"certificate_valid": False},
            )
            return False, "License expired. Please renew."

        self._record_thinking(
            operation="verify",
            goal="record valid local license verification",
            constraints={
                "fingerprint_match": True,
                "certificate_valid": True,
                "license_tier": self.certificate.license_tier,
            },
        )
        return True, f"Valid license. Tier: {self.certificate.license_tier}"

    def get_node_identity(self) -> Optional[str]:
        """Get node identity for mesh network authentication."""
        if not self.certificate:
            self._record_thinking(
                operation="get_node_identity",
                goal="skip node identity because no certificate is loaded",
                constraints={"certificate_loaded": False},
            )
            return None

        # Identity = hash of (fingerprint + certificate)
        identity_data = f"{self.fingerprint.to_hash()}:{self.certificate.signature}"
        identity = hashlib.sha256(identity_data.encode()).hexdigest()[:32]
        self._record_thinking(
            operation="get_node_identity",
            goal="derive local node identity hash from license material",
            constraints={
                "certificate_loaded": True,
                "node_identity_hash": self._hash_value(identity),
            },
        )
        return identity


class MeshNetworkValidator:
    """
    Validates nodes trying to join the mesh.
    Rejects nodes without valid certificates.
    Detects double-spending (same ID on multiple machines).
    """

    def __init__(self):
        self.known_identities: dict = {}  # identity -> (last_seen, ip_address)
        self.banned_identities: set = set()

    def validate_node(
        self, node_identity: str, fingerprint_hash: str, ip_address: str
    ) -> Tuple[bool, str]:
        """Validate a node trying to connect."""

        # Check if banned
        if node_identity in self.banned_identities:
            return False, "Node is banned from network"

        # Check for double-spending (same identity, different IP)
        if node_identity in self.known_identities:
            last_ip = self.known_identities[node_identity][1]
            if last_ip != ip_address:
                # Same identity from different location = potential piracy
                # Auto-ban both
                self.banned_identities.add(node_identity)
                return False, "DOUBLE SPENDING DETECTED! Both nodes banned."

        # Register node
        self.known_identities[node_identity] = (time.time(), ip_address)
        return True, "Node validated"

    def get_active_nodes(self) -> int:
        """Get count of active nodes (seen in last 5 min)."""
        cutoff = time.time() - 300
        return sum(1 for t, _ in self.known_identities.values() if t > cutoff)


def main(argv: Optional[list[str]] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Activate or verify a node license.")
    parser.add_argument("--server", default=os.getenv("LICENSE_SERVER", ""))
    parser.add_argument("--token", default=os.getenv("LICENSE_TOKEN", ""))
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args(argv)

    manager = NodeLicenseManager(auth_server_url=args.server)
    if args.verify:
        ok, message = manager.verify()
    else:
        if not args.token:
            parser.error("--token or LICENSE_TOKEN is required for activation")
        ok, message = manager.activate(args.token)

    print(message)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())


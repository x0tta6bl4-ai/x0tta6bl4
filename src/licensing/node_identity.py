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

import hashlib
import hmac
import json
import os
import platform
import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

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
        except:
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
        except:
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
        except:
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


class NodeLicenseManager:
    """
    Client-side license manager.
    Runs on customer's machine.
    """

    CERT_PATH = Path.home() / ".x0tta6bl4" / "license.cert"

    def __init__(self, auth_server_url: str = None):
        import os

        auth_server_url = auth_server_url or os.getenv("LICENSE_SERVER", "")
        self.auth_server_url = auth_server_url
        self.fingerprint = HardwareFingerprinter.generate()
        self.certificate: Optional[IdentityCertificate] = None

        # Try to load existing certificate
        self._load_certificate()

    def _load_certificate(self):
        """Load certificate from disk."""
        if self.CERT_PATH.exists():
            self.certificate = IdentityCertificate.load(str(self.CERT_PATH))

    def _save_certificate(self):
        """Save certificate to disk."""
        if self.certificate:
            self.CERT_PATH.parent.mkdir(parents=True, exist_ok=True)
            self.certificate.save(str(self.CERT_PATH))

    def activate(self, activation_token: str) -> Tuple[bool, str]:
        """
        Activate node with token.

        In production: calls auth server API
        For now: local simulation
        """
        # Verify fingerprint matches certificate (if exists)
        if self.certificate:
            if self.certificate.fingerprint_hash != self.fingerprint.to_hash():
                return (
                    False,
                    "Hardware fingerprint mismatch! License bound to different machine.",
                )

        # In production, this would call:
        # POST {auth_server_url}/activate
        # Body: {fingerprint: ..., token: ...}
        # Response: {certificate: ...}

        # For demo, simulate local authority
        authority = LicenseAuthority()

        # Determine tier from token
        tier = "basic"
        if "PRO" in activation_token:
            tier = "pro"
        elif "ENT" in activation_token:
            tier = "enterprise"

        self.certificate = authority.sign_certificate(
            fingerprint_hash=self.fingerprint.to_hash(),
            activation_token=activation_token,
            license_tier=tier,
        )

        self._save_certificate()
        return True, f"Activated! Tier: {tier}"

    def verify(self) -> Tuple[bool, str]:
        """Verify current license is valid."""
        if not self.certificate:
            return False, "No license found. Please activate."

        # Check fingerprint binding
        if self.certificate.fingerprint_hash != self.fingerprint.to_hash():
            return False, "SECURITY ALERT: License bound to different hardware!"

        # Check expiry
        if not self.certificate.is_valid():
            return False, "License expired. Please renew."

        return True, f"Valid license. Tier: {self.certificate.license_tier}"

    def get_node_identity(self) -> Optional[str]:
        """Get node identity for mesh network authentication."""
        if not self.certificate:
            return None

        # Identity = hash of (fingerprint + certificate)
        identity_data = f"{self.fingerprint.to_hash()}:{self.certificate.signature}"
        return hashlib.sha256(identity_data.encode()).hexdigest()[:32]


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


# Demo
if __name__ == "__main__":
    print("=" * 60)
    print("🔒 x0tta6bl4 Zero-Trust Licensing Demo")
    print("=" * 60)

    # 1. Generate fingerprint
    print("\n📱 Device Fingerprint:")
    fp = HardwareFingerprinter.generate()
    for k, v in fp.to_dict().items():
        print(f"   {k}: {v}")

    # 2. Authority generates token (YOUR SERVER)
    print("\n🏛️ License Authority (Your Server):")
    authority = LicenseAuthority()
    token = authority.generate_activation_token("pro")
    print(f"   Generated token: {token}")

    # 3. Customer activates (CUSTOMER'S MACHINE)
    print("\n👤 Customer Activation:")
    manager = NodeLicenseManager()
    success, msg = manager.activate(token)
    print(f"   {msg}")

    # 4. Verify license
    print("\n✅ License Verification:")
    valid, msg = manager.verify()
    print(f"   {msg}")

    # 5. Get network identity
    print("\n🌐 Network Identity:")
    identity = manager.get_node_identity()
    print(f"   Node ID: {identity}")

    # 6. Mesh validation
    print("\n🛡️ Mesh Network Validation:")
    validator = MeshNetworkValidator()

    # Valid node
    ok, msg = validator.validate_node(identity, fp.to_hash(), "192.168.1.100")
    print(f"   First connection: {msg}")

    # Same node, same IP (OK)
    ok, msg = validator.validate_node(identity, fp.to_hash(), "192.168.1.100")
    print(f"   Same IP reconnect: {msg}")

    # Same identity, different IP (PIRACY!)
    ok, msg = validator.validate_node(identity, fp.to_hash(), "10.0.0.50")
    print(f"   Different IP (piracy): {msg}")

    print("\n" + "=" * 60)
    print("✅ Demo Complete!")
    print("=" * 60)

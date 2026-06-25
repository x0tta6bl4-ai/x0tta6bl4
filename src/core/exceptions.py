"""
x0tta6bl4 — Centralized exception hierarchy.

All project-specific exceptions inherit from X0tBaseError.
This allows callers to catch *any* project error with a single
``except X0tBaseError`` while still handling specific cases.

Migration note:
  Existing modules define their own exception classes inherited
  directly from ``Exception``. Those should be gradually migrated
  to inherit from the appropriate class in this hierarchy.
  The new classes are available immediately for new code.
"""


class X0tBaseError(Exception):
    """Base exception for all x0tta6bl4 project errors."""

    pass


# ── Configuration ──────────────────────────────────────────────────


class ConfigError(X0tBaseError):
    """Configuration or settings error."""

    pass


# ── Network / Transport ────────────────────────────────────────────


class NetworkError(X0tBaseError):
    """Generic network-layer error."""

    pass


class MeshError(NetworkError):
    """Mesh routing / topology error."""

    pass


class TransportError(NetworkError):
    """Wire transport or tunnel error."""

    pass


class VPNError(NetworkError):
    """VPN-specific error (tunnel, handshake, discovery)."""

    pass


# ── Cryptography / PQC ─────────────────────────────────────────────


class CryptoError(X0tBaseError):
    """Cryptographic operation error."""

    pass


class PQCError(CryptoError):
    """Post-quantum cryptography error (ML-KEM, ML-DSA)."""

    pass


class KeyManagementError(CryptoError):
    """Key generation, storage, or rotation error."""

    pass


# ── Authentication / Authorisation ──────────────────────────────────


class AuthError(X0tBaseError):
    """Authentication or authorisation error."""

    pass


class TokenExpiredError(AuthError):
    """Token has expired and requires refresh."""

    pass


class PermissionDeniedError(AuthError):
    """Caller lacks required permissions."""

    pass


# ── Billing ─────────────────────────────────────────────────────────


class BillingError(X0tBaseError):
    """Billing / payment / invoice error."""

    pass


# ── Storage ─────────────────────────────────────────────────────────


class StorageError(X0tBaseError):
    """Database or persistent storage error."""

    pass


# ── MAPE-K (Self-Healing) ──────────────────────────────────────────


class MAPEKError(X0tBaseError):
    """MAPE-K autonomic loop error."""

    pass


# ── Service / Integration ──────────────────────────────────────────


class ServiceError(X0tBaseError):
    """Internal service or integration error."""

    pass


class DependencyError(ServiceError):
    """External dependency failure (database, queue, 3rd-party API)."""

    pass


# ── Security ────────────────────────────────────────────────────────


class SecurityError(X0tBaseError):
    """Security policy enforcement error."""

    pass


class ValidationError(X0tBaseError):
    """Input validation error."""

    pass


# ── eBPF ────────────────────────────────────────────────────────────


class EBPFError(X0tBaseError):
    """eBPF program load, attach, or runtime error."""

    pass


__all__ = [
    "X0tBaseError",
    "ConfigError",
    "NetworkError",
    "MeshError",
    "TransportError",
    "VPNError",
    "CryptoError",
    "PQCError",
    "KeyManagementError",
    "AuthError",
    "TokenExpiredError",
    "PermissionDeniedError",
    "BillingError",
    "StorageError",
    "MAPEKError",
    "ServiceError",
    "DependencyError",
    "SecurityError",
    "ValidationError",
    "EBPFError",
]

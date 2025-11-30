"""mTLS TLS context helpers for SPIFFE X509SVID identities.

This module provides a minimal TLS context builder around Python's
standard :mod:`ssl` library. It is intentionally conservative and does
not attempt to load certificate material from the in-memory SVID, since
most test and mock environments use placeholder certificates. Instead it
creates a configured :class:`ssl.SSLContext` with sane defaults for
TLS 1.3 and mutual authentication, and associates it with a SPIFFE ID.

This design keeps the integration points for future hardening (actual
certificate/key loading and trust bundle management) while remaining
safe to use in unit tests and local development.
"""

from __future__ import annotations

import ssl
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from ..workload import X509SVID


class TLSRole(str, Enum):
    """Role of the endpoint in an mTLS connection."""

    CLIENT = "client"
    SERVER = "server"


@dataclass
class MTLSContext:
    """Container for an mTLS SSLContext bound to a SPIFFE identity.

    Attributes:
        role: Whether this context is used on the client or server side.
        ssl_context: Underlying :class:`ssl.SSLContext` instance.
        spiffe_id: SPIFFE ID associated with the local workload.
    """

    role: TLSRole
    ssl_context: ssl.SSLContext
    spiffe_id: str


def build_mtls_context(identity: X509SVID, role: TLSRole = TLSRole.CLIENT) -> MTLSContext:
    """Build a minimal mTLS-capable TLS context for the given identity.

    The returned context is configured for TLS 1.3 and mutual
    authentication (``CERT_REQUIRED``). It does **not** load the
    in-memory certificate chain or private key from ``identity`` yet;
    that work belongs to later hardening stages where real SVID
    material is wired into the TLS stack.
    """

    purpose = ssl.Purpose.SERVER_AUTH if role is TLSRole.CLIENT else ssl.Purpose.CLIENT_AUTH
    ctx = ssl.create_default_context(purpose=purpose)

    # Prefer TLS 1.3 where available.
    try:
        ctx.minimum_version = ssl.TLSVersion.TLSv1_3  # type: ignore[attr-defined]
    except Exception:
        # Older Python versions may not expose TLSVersion; rely on
        # library defaults in that case.
        pass

    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_REQUIRED

    return MTLSContext(role=role, ssl_context=ctx, spiffe_id=identity.spiffe_id)

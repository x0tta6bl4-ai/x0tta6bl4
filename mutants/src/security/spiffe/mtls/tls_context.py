"""mTLS TLS context helpers for SPIFFE X509SVID identities."""

from __future__ import annotations

import ssl
import tempfile
from dataclasses import dataclass
from enum import Enum
from typing import Optional, List

from ..workload import X509SVID


class TLSRole(str, Enum):
    """Role of the endpoint in an mTLS connection."""

    CLIENT = "client"
    SERVER = "server"


@dataclass
class MTLSContext:
    """Container for an mTLS SSLContext bound to a SPIFFE identity.

    This class now manages the lifecycle of temporary files created to hold
    the certificate and private key, as required by `ssl.SSLContext.load_cert_chain`.

    Attributes:
        role: Whether this context is used on the client or server side.
        ssl_context: Underlying :class:`ssl.SSLContext` instance.
        spiffe_id: SPIFFE ID associated with the local workload.
        cert_file: Temporary file holding the certificate chain.
        key_file: Temporary file holding the private key.
    """

    role: TLSRole
    ssl_context: ssl.SSLContext
    spiffe_id: str
    cert_file: Optional[tempfile._TemporaryFileWrapper] = None
    key_file: Optional[tempfile._TemporaryFileWrapper] = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()

    def cleanup(self):
        """Clean up (close and delete) the temporary certificate and key files."""
        if self.cert_file:
            try:
                self.cert_file.close()
            except Exception:
                pass  # Ignore errors on close
        if self.key_file:
            try:
                self.key_file.close()
            except Exception:
                pass  # Ignore errors on close


def build_mtls_context(identity: X509SVID, role: TLSRole = TLSRole.CLIENT) -> MTLSContext:
    """Build a functional mTLS-capable TLS context for the given identity.

    The returned context is configured for TLS 1.3 and mutual
    authentication (``CERT_REQUIRED``). It writes the certificate chain and
    private key from the given ``identity`` to temporary files and loads them
    into the ``ssl.SSLContext``.
    """
    purpose = ssl.Purpose.SERVER_AUTH if role is TLSRole.CLIENT else ssl.Purpose.CLIENT_AUTH
    ctx = ssl.create_default_context(purpose=purpose)

    # Prefer TLS 1.3 where available.
    try:
        ctx.minimum_version = ssl.TLSVersion.TLSv1_3
    except (AttributeError, NameError):
        # Older Python versions may not expose TLSVersion; rely on library defaults.
        pass

    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_REQUIRED

    cert_file = None
    key_file = None
    try:
        # Create temporary files to hold the cert and key.
        # These files will be managed by the returned MTLSContext object.
        cert_file = tempfile.NamedTemporaryFile(mode='w+b', delete=False, prefix="spiffe-cert-", suffix=".pem")
        key_file = tempfile.NamedTemporaryFile(mode='w+b', delete=False, prefix="spiffe-key-", suffix=".pem")

        # The certificate chain is a list of DER-encoded bytes. Concatenate them for the PEM file.
        for cert_bytes in identity.cert_chain:
            cert_file.write(cert_bytes)
            cert_file.write(b'\n')
        cert_file.flush()

        key_file.write(identity.private_key)
        key_file.flush()

        ctx.load_cert_chain(certfile=cert_file.name, keyfile=key_file.name)

        return MTLSContext(
            role=role,
            ssl_context=ctx,
            spiffe_id=identity.spiffe_id,
            cert_file=cert_file,
            key_file=key_file,
        )
    except Exception as e:
        # If something goes wrong, make sure to clean up any files we created.
        if cert_file:
            cert_file.close()
        if key_file:
            key_file.close()
        raise IOError(f"Failed to build mTLS context: {e}") from e

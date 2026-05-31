"""
Domain Fronting Transport for x0tta6bl4 Mesh.
Encapsulates traffic in HTTP-looking requests.
"""

from __future__ import annotations

import hashlib
import logging
import socket
import ssl
import time
from typing import Any, Dict, Optional

from src.coordination.events import EventBus, EventType, get_event_bus
from src.services.service_event_identity import service_event_identity
from .base import ObfuscationTransport

logger = logging.getLogger(__name__)

_SERVICE_AGENT = "domain-fronting-transport"
_SERVICE_LAYER = "network_domain_fronting_transport_local_evidence"
DOMAIN_FRONTING_CLAIM_BOUNDARY = (
    "Local domain-fronting transport evidence only. It records local HTTP "
    "encapsulation/decapsulation, TLS wrapping attempts, byte-count buckets, "
    "duration, redacted front/backend domain hashes, and service identity "
    "presence; it does not expose payload bytes, raw domains, socket peer "
    "addresses, TLS secrets, or prove CDN acceptance, DPI bypass, censorship "
    "bypass, remote reachability, packet delivery, anonymity, provider health, "
    "client installation, or production customer traffic use."
)


def _sha256_prefix(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    if not text:
        return None
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]


def _byte_count_bucket(value: Any) -> str:
    if not isinstance(value, int) or value <= 0:
        return "zero"
    if value <= 64:
        return "tiny"
    if value <= 512:
        return "small"
    if value <= 1500:
        return "mtu"
    if value <= 8192:
        return "chunk"
    return "large"


def _parse_content_length(headers: bytes) -> Optional[int]:
    for line in headers.split(b"\r\n"):
        if b":" not in line:
            continue
        name, value = line.split(b":", 1)
        if name.strip().lower() != b"content-length":
            continue
        try:
            return max(0, int(value.strip()))
        except ValueError:
            return None
    return None


def _extract_http_body(buffer: bytes) -> tuple[Optional[bytes], bytes]:
    header_end = buffer.find(b"\r\n\r\n")
    if header_end == -1:
        return None, buffer

    headers = buffer[:header_end]
    body_start = header_end + 4
    content_length = _parse_content_length(headers)
    if content_length is None:
        return buffer[body_start:], b""

    body_end = body_start + content_length
    if len(buffer) < body_end:
        return None, buffer
    return buffer[body_start:body_end], buffer[body_end:]


class DomainFrontingSocket(socket.socket):
    """
    Socket wrapper that performs Domain Fronting.
    1. Wraps connection in real TLS with 'front' SNI.
    2. Encapsulates writes in HTTP POST requests with 'backend' Host header.
    3. Decapsulates reads from HTTP Responses.
    """

    def __init__(
        self,
        sock: socket.socket,
        transport: "DomainFrontingTransport",
        tls_sock: socket.socket,
    ):
        self._raw_sock = sock
        self._tls_sock = tls_sock
        self._transport = transport
        self._buffer = b""

        try:
            super().__init__(fileno=sock.fileno())
        except Exception:
            pass
        self.timeout = sock.gettimeout()

    def send(self, data: bytes, flags=0) -> int:
        # Encapsulate in HTTP POST
        # Each send is framed as a discrete HTTP request for this transport mode.

        body = data
        headers = (
            f"POST /data HTTP/1.1\r\n"
            f"Host: {self._transport.backend_domain}\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)\r\n"
            f"Connection: keep-alive\r\n"
            f"\r\n"
        ).encode("ascii")

        full_packet = headers + body

        # Send over TLS socket
        try:
            self._tls_sock.sendall(full_packet)
            return len(data)  # Return original length to satisfy socket interface
        except ssl.SSLError as e:
            # Handle TLS errors
            raise socket.error(f"TLS Error: {e}")

    def recv(self, bufsize: int, flags=0) -> bytes:
        # We need to read HTTP responses and extract body.
        # HTTP/1.1 200 OK ... \r\n\r\n[BODY]

        try:
            body, remaining = _extract_http_body(self._buffer)
            if body is not None:
                self._buffer = remaining
                return body

            # Read chunk from TLS
            chunk = self._tls_sock.recv(bufsize)
            if not chunk:
                return b""

            self._buffer += chunk

            body, remaining = _extract_http_body(self._buffer)
            if body is None:
                return b""
            self._buffer = remaining
            return body

        except ssl.SSLError as e:
            if e.errno == ssl.SSL_ERROR_WANT_READ:
                return b""
            raise socket.error(f"TLS Error: {e}")

    def close(self):
        self._tls_sock.close()

    def __getattr__(self, name):
        return getattr(self._tls_sock, name)


class DomainFrontingTransport(ObfuscationTransport):
    """
    Domain Fronting Transport.
    Connects via TLS to a CDN IP, but masquerades as a legit domain (SNI).
    The Host header targets the hidden backend.
    
    Security Note (CVE-2026-DF-001 fix):
    SSL certificate verification is ENABLED for the front domain (CDN).
    This prevents MITM attacks between client and CDN.
    The backend authentication is handled via mTLS inside the tunnel.
    """

    def __init__(
        self,
        front_domain: str,
        backend_domain: Optional[str] = None,
        *,
        backend_host: Optional[str] = None,
        verify_mode: int = ssl.CERT_REQUIRED,
        ca_bundle: Optional[str] = None,
        event_bus: Optional[EventBus] = None,
        event_project_root: Optional[str] = None,
    ):
        self.event_bus = event_bus
        self.event_project_root = event_project_root
        self.front_domain = front_domain
        if backend_domain and backend_host and backend_domain != backend_host:
            raise ValueError("backend_domain and backend_host must match when both provided")
        self.backend_domain = backend_domain or backend_host
        if not self.backend_domain:
            raise ValueError("backend_domain (or backend_host) is required")

        # CVE-2026-DF-001: explicitly reject insecure verification mode.
        if verify_mode == ssl.CERT_NONE:
            raise ValueError("ssl.CERT_NONE is not allowed for DomainFrontingTransport")

        # Setup SSL Context with PROPER certificate verification
        # CVE-2026-DF-001: Never use ssl.CERT_NONE in production
        if ca_bundle:
            self.context = ssl.create_default_context(cafile=ca_bundle)
        else:
            self.context = ssl.create_default_context()
        
        # Verify the front domain certificate (CDN certificate)
        self.context.check_hostname = True
        self.context.verify_mode = verify_mode
        
        # Enforce minimum TLS 1.2
        self.context.minimum_version = ssl.TLSVersion.TLSv1_2
        
        logger.info(
            f"DomainFrontingTransport initialized with SSL verification enabled "
            f"(verify_mode={verify_mode}, check_hostname=True, front_domain={front_domain})"
        )

    def _event_bus_or_none(self) -> Optional[EventBus]:
        if self.event_bus is not None:
            return self.event_bus
        if self.event_project_root is None:
            return None
        try:
            self.event_bus = get_event_bus(self.event_project_root)
            return self.event_bus
        except Exception as exc:
            logger.error("Failed to initialize domain-fronting EventBus: %s", exc)
            return None

    def _identity_presence(self) -> Dict[str, bool]:
        identity = service_event_identity(service_name=_SERVICE_AGENT)
        return {
            "spiffe_id_present": bool(identity.get("spiffe_id")),
            "did_present": bool(identity.get("did")),
            "wallet_address_present": bool(identity.get("wallet_address")),
            "raw_identity_redacted": True,
        }

    def _domain_metadata(self) -> Dict[str, Any]:
        return {
            "front_present": bool(self.front_domain),
            "front_hash": _sha256_prefix(self.front_domain),
            "backend_present": bool(self.backend_domain),
            "backend_hash": _sha256_prefix(self.backend_domain),
            "raw_domains_redacted": True,
        }

    def _publish_evidence(
        self,
        *,
        operation: str,
        status_value: str,
        started_at: float,
        metadata: Optional[Dict[str, Any]] = None,
        error_type: Optional[str] = None,
    ) -> Optional[str]:
        bus = self._event_bus_or_none()
        if bus is None:
            return None

        payload: Dict[str, Any] = {
            "component": "network.obfuscation.domain_fronting",
            "operation": operation,
            "service_name": _SERVICE_AGENT,
            "source_alias": _SERVICE_AGENT,
            "layer": _SERVICE_LAYER,
            "status": status_value,
            "duration_ms": round((time.monotonic() - started_at) * 1000.0, 3),
            "domains": self._domain_metadata(),
            "service_identity": self._identity_presence(),
            "control_action": False,
            "observed_state": True,
            "payloads_redacted": True,
            "raw_identifiers_redacted": True,
            "raw_domains_redacted": True,
            "dataplane_confirmed": False,
            "dpi_bypass_confirmed": False,
            "bypass_confirmed": False,
            "claim_boundary": DOMAIN_FRONTING_CLAIM_BOUNDARY,
        }
        if metadata:
            payload.update(metadata)
        if error_type:
            payload["error"] = {
                "type": error_type,
                "message_redacted": True,
            }

        event_type = (
            EventType.TASK_FAILED
            if status_value == "failed"
            else EventType.PIPELINE_STAGE_END
        )
        try:
            event = bus.publish(event_type, _SERVICE_AGENT, payload, priority=4)
            return event.event_id
        except Exception as exc:
            logger.error("Failed to publish domain-fronting evidence: %s", exc)
            return None

    def wrap_socket(self, sock: socket.socket) -> socket.socket:
        started_at = time.monotonic()
        # Wrap in real TLS with SNI = front_domain
        try:
            tls_sock = self.context.wrap_socket(
                sock, server_hostname=self.front_domain, do_handshake_on_connect=True
            )
            wrapped = DomainFrontingSocket(sock, self, tls_sock)
        except Exception as exc:
            self._publish_evidence(
                operation="wrap_socket",
                status_value="failed",
                started_at=started_at,
                metadata={
                    "tls": {
                        "attempted": True,
                        "verify_mode": str(self.context.verify_mode),
                        "check_hostname": bool(self.context.check_hostname),
                        "raw_peer_redacted": True,
                    },
                },
                error_type=type(exc).__name__,
            )
            raise

        self._publish_evidence(
            operation="wrap_socket",
            status_value="wrapped",
            started_at=started_at,
            metadata={
                "tls": {
                    "attempted": True,
                    "verify_mode": str(self.context.verify_mode),
                    "check_hostname": bool(self.context.check_hostname),
                    "raw_peer_redacted": True,
                },
            },
        )
        return wrapped

    def obfuscate(self, data: bytes) -> bytes:
        started_at = time.monotonic()
        headers = (
            f"POST /data HTTP/1.1\r\n"
            f"Host: {self.backend_domain}\r\n"
            f"Content-Length: {len(data)}\r\n"
            f"\r\n"
        ).encode("ascii")
        packet = headers + data
        self._publish_evidence(
            operation="obfuscate",
            status_value="encapsulated",
            started_at=started_at,
            metadata={
                "http": {
                    "method": "POST",
                    "host_header_present": True,
                    "content_length_present": True,
                    "headers_bytes_bucket": _byte_count_bucket(len(headers)),
                    "body_bytes_bucket": _byte_count_bucket(len(data)),
                    "output_bytes_bucket": _byte_count_bucket(len(packet)),
                    "raw_http_redacted": True,
                },
            },
        )
        return packet

    def deobfuscate(self, data: bytes) -> bytes:
        started_at = time.monotonic()
        # Strip headers
        if data.find(b"\r\n\r\n") != -1:
            body, _remaining = _extract_http_body(data)
            result = body or b""
            self._publish_evidence(
                operation="deobfuscate",
                status_value="decapsulated",
                started_at=started_at,
                metadata={
                    "http": {
                        "headers_present": True,
                        "body_bytes_bucket": _byte_count_bucket(len(result)),
                        "input_bytes_bucket": _byte_count_bucket(len(data)),
                        "raw_http_redacted": True,
                    },
                },
            )
            return result
        self._publish_evidence(
            operation="deobfuscate",
            status_value="pass_through",
            started_at=started_at,
            metadata={
                "http": {
                    "headers_present": False,
                    "input_bytes_bucket": _byte_count_bucket(len(data)),
                    "body_bytes_bucket": _byte_count_bucket(len(data)),
                    "raw_http_redacted": True,
                },
            },
        )
        return data

"""
HTTP steganography helpers for experimental transport obfuscation.

This module only implements reversible payload packing/unpacking inside
HTTP-looking requests. It does not claim guaranteed DPI bypass.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import logging
import random
import time
import urllib.parse
from typing import Any, Dict, Optional

from src.coordination.events import EventBus, EventType, get_event_bus
from src.services.service_event_identity import service_event_identity


logger = logging.getLogger(__name__)

_SERVICE_AGENT = "http-steganography-transport"
_SERVICE_LAYER = "network_http_steganography_local_evidence"
HTTP_STEGANOGRAPHY_CLAIM_BOUNDARY = (
    "Local HTTP steganography helper evidence only. It records local "
    "encapsulation/decapsulation metadata, duration, byte-count buckets, "
    "redacted target URL hashes, query-shape metadata, and service identity "
    "presence; it does not expose payload bytes, raw URLs, query values, "
    "HTTP headers, user-agent strings, or prove DPI bypass, censorship bypass, "
    "remote reachability, packet delivery, anonymity, provider health, client "
    "installation, or production customer traffic use."
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
    if value <= HTTPSteganography.MAX_DATA_BYTES:
        return "max_payload"
    return "too_large"


def _target_url_metadata(target_url: str) -> Dict[str, Any]:
    parsed = urllib.parse.urlparse(target_url)
    return {
        "scheme": parsed.scheme or None,
        "host_present": bool(parsed.netloc),
        "host_hash": _sha256_prefix(parsed.netloc),
        "path_present": bool(parsed.path),
        "path_hash": _sha256_prefix(parsed.path),
        "query_present": bool(parsed.query),
        "raw_target_url_redacted": True,
    }


class HTTPSteganography:
    """
    Encode/decode opaque bytes into HTTP query parameters.

    The class is intentionally conservative:
    - uses URL-safe base64
    - validates payload size
    - never raises on malformed input in decapsulate()
    """

    # Keep packet size bounded to avoid memory abuse through query params.
    MAX_DATA_BYTES = 32 * 1024

    COMMON_UA = [
        (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/17.2 Safari/605.1.15"
        ),
    ]

    def __init__(
        self,
        event_bus: Optional[EventBus] = None,
        event_project_root: Optional[str] = None,
    ):
        self.event_bus = event_bus
        self.event_project_root = event_project_root

    def _event_bus_or_none(self) -> Optional[EventBus]:
        if self.event_bus is not None:
            return self.event_bus
        if self.event_project_root is None:
            return None
        try:
            self.event_bus = get_event_bus(self.event_project_root)
            return self.event_bus
        except Exception as exc:
            logger.error("Failed to initialize HTTP steganography EventBus: %s", exc)
            return None

    def _identity_presence(self) -> Dict[str, bool]:
        identity = service_event_identity(service_name=_SERVICE_AGENT)
        return {
            "spiffe_id_present": bool(identity.get("spiffe_id")),
            "did_present": bool(identity.get("did")),
            "wallet_address_present": bool(identity.get("wallet_address")),
            "raw_identity_redacted": True,
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
            "component": "network.obfuscation.http_steganography",
            "operation": operation,
            "service_name": _SERVICE_AGENT,
            "source_alias": _SERVICE_AGENT,
            "layer": _SERVICE_LAYER,
            "status": status_value,
            "duration_ms": round((time.monotonic() - started_at) * 1000.0, 3),
            "service_identity": self._identity_presence(),
            "control_action": False,
            "observed_state": True,
            "payloads_redacted": True,
            "raw_identifiers_redacted": True,
            "raw_query_values_redacted": True,
            "raw_headers_redacted": True,
            "dataplane_confirmed": False,
            "dpi_bypass_confirmed": False,
            "bypass_confirmed": False,
            "claim_boundary": HTTP_STEGANOGRAPHY_CLAIM_BOUNDARY,
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
            logger.error("Failed to publish HTTP steganography evidence: %s", exc)
            return None

    def encapsulate(
        self, data: bytes, target_url: str = "https://www.google.com/search"
    ) -> Dict[str, Any]:
        """
        Pack binary payload as HTTP GET query arguments.
        """
        started_at = time.monotonic()
        if not isinstance(data, (bytes, bytearray)):
            self._publish_evidence(
                operation="encapsulate",
                status_value="failed",
                started_at=started_at,
                metadata={
                    "target_url": _target_url_metadata(target_url),
                    "input": {
                        "bytes_like": False,
                        "input_bytes_bucket": "not_bytes_like",
                    },
                },
                error_type="TypeError",
            )
            raise TypeError("data must be bytes-like")
        if len(data) > self.MAX_DATA_BYTES:
            self._publish_evidence(
                operation="encapsulate",
                status_value="failed",
                started_at=started_at,
                metadata={
                    "target_url": _target_url_metadata(target_url),
                    "input": {
                        "bytes_like": True,
                        "input_bytes_bucket": _byte_count_bucket(len(data)),
                        "max_data_bytes": self.MAX_DATA_BYTES,
                    },
                },
                error_type="ValueError",
            )
            raise ValueError(
                f"payload too large: {len(data)} bytes (max {self.MAX_DATA_BYTES})"
            )

        encoded = base64.urlsafe_b64encode(bytes(data)).decode("ascii").rstrip("=")
        params = {
            "q": "network+telemetry+request",
            # split field to mimic multi-parameter apps
            "x0t_id": encoded[:32],
            "payload": encoded[32:],
        }

        full_url = f"{target_url}?{urllib.parse.urlencode(params)}"
        request = {
            "method": "GET",
            "url": full_url,
            "headers": {
                "User-Agent": random.choice(self.COMMON_UA),
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;q=0.9,"
                    "*/*;q=0.8"
                ),
                "Accept-Language": "en-US,en;q=0.5",
                "Referer": "https://www.google.com/",
            },
        }
        self._publish_evidence(
            operation="encapsulate",
            status_value="encapsulated",
            started_at=started_at,
            metadata={
                "target_url": _target_url_metadata(target_url),
                "http": {
                    "method": "GET",
                    "query_params_total": len(params),
                    "payload_param_present": True,
                    "id_param_present": True,
                    "headers_total": 4,
                    "user_agent_profile_count": len(self.COMMON_UA),
                    "raw_headers_redacted": True,
                },
                "input_bytes_bucket": _byte_count_bucket(len(data)),
                "encoded_bytes_bucket": _byte_count_bucket(len(encoded)),
                "url_bytes_bucket": _byte_count_bucket(len(full_url)),
            },
        )
        return request

    def decapsulate(self, request_params: Dict[str, str]) -> bytes:
        """
        Unpack binary payload from query params.

        Returns empty bytes on malformed/oversized input.
        """
        started_at = time.monotonic()
        x0t_id = request_params.get("x0t_id", "")
        payload = request_params.get("payload", "")
        full_b64 = f"{x0t_id}{payload}".strip()
        if not full_b64:
            self._publish_evidence(
                operation="decapsulate",
                status_value="empty_input",
                started_at=started_at,
                metadata={
                    "query": {
                        "params_total": len(request_params),
                        "id_param_present": bool(x0t_id),
                        "payload_param_present": bool(payload),
                        "encoded_bytes_bucket": "zero",
                        "raw_query_values_redacted": True,
                    },
                    "output_bytes_bucket": "zero",
                },
            )
            return b""

        # Approx upper bound for url-safe base64 encoded payload length.
        max_encoded_len = ((self.MAX_DATA_BYTES + 2) // 3) * 4
        if len(full_b64) > max_encoded_len:
            self._publish_evidence(
                operation="decapsulate",
                status_value="rejected_oversized",
                started_at=started_at,
                metadata={
                    "query": {
                        "params_total": len(request_params),
                        "id_param_present": bool(x0t_id),
                        "payload_param_present": bool(payload),
                        "encoded_bytes_bucket": _byte_count_bucket(len(full_b64)),
                        "max_encoded_bytes": max_encoded_len,
                        "raw_query_values_redacted": True,
                    },
                    "output_bytes_bucket": "zero",
                },
            )
            return b""

        # restore stripped padding
        padding = "=" * ((4 - (len(full_b64) % 4)) % 4)
        try:
            decoded = base64.b64decode(
                full_b64 + padding,
                altchars=b"-_",
                validate=True,
            )
        except (binascii.Error, ValueError):
            self._publish_evidence(
                operation="decapsulate",
                status_value="malformed",
                started_at=started_at,
                metadata={
                    "query": {
                        "params_total": len(request_params),
                        "id_param_present": bool(x0t_id),
                        "payload_param_present": bool(payload),
                        "encoded_bytes_bucket": _byte_count_bucket(len(full_b64)),
                        "raw_query_values_redacted": True,
                    },
                    "output_bytes_bucket": "zero",
                },
                error_type="Base64DecodeError",
            )
            return b""
        self._publish_evidence(
            operation="decapsulate",
            status_value="decapsulated",
            started_at=started_at,
            metadata={
                "query": {
                    "params_total": len(request_params),
                    "id_param_present": bool(x0t_id),
                    "payload_param_present": bool(payload),
                    "encoded_bytes_bucket": _byte_count_bucket(len(full_b64)),
                    "raw_query_values_redacted": True,
                },
                "output_bytes_bucket": _byte_count_bucket(len(decoded)),
            },
        )
        return decoded


# Global instance
http_steganography = HTTPSteganography()

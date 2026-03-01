"""
HTTP steganography helpers for experimental transport obfuscation.

This module only implements reversible payload packing/unpacking inside
HTTP-looking requests. It does not claim guaranteed DPI bypass.
"""

from __future__ import annotations

import base64
import binascii
import random
import urllib.parse
from typing import Any, Dict


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

    def encapsulate(
        self, data: bytes, target_url: str = "https://www.google.com/search"
    ) -> Dict[str, Any]:
        """
        Pack binary payload as HTTP GET query arguments.
        """
        if not isinstance(data, (bytes, bytearray)):
            raise TypeError("data must be bytes-like")
        if len(data) > self.MAX_DATA_BYTES:
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
        return {
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

    def decapsulate(self, request_params: Dict[str, str]) -> bytes:
        """
        Unpack binary payload from query params.

        Returns empty bytes on malformed/oversized input.
        """
        x0t_id = request_params.get("x0t_id", "")
        payload = request_params.get("payload", "")
        full_b64 = f"{x0t_id}{payload}".strip()
        if not full_b64:
            return b""

        # Approx upper bound for url-safe base64 encoded payload length.
        max_encoded_len = ((self.MAX_DATA_BYTES + 2) // 3) * 4
        if len(full_b64) > max_encoded_len:
            return b""

        # restore stripped padding
        padding = "=" * ((4 - (len(full_b64) % 4)) % 4)
        try:
            return base64.b64decode(
                full_b64 + padding,
                altchars=b"-_",
                validate=True,
            )
        except (binascii.Error, ValueError):
            return b""


# Global instance
http_steganography = HTTPSteganography()


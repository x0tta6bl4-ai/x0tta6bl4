"""Utility functions for x402 paid API endpoint validation."""
from __future__ import annotations

import base64
import ipaddress
import json
import re
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from datetime import datetime, timezone
from typing import Any


SECRET_PATTERN = re.compile(
    r"(api[_-]?key|private[_-]?key|secret|token|password|bearer\s+[a-z0-9._-]+)",
    re.IGNORECASE,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def price_to_micro_usdc(price: str | float | int) -> int:
    if isinstance(price, (int, float)):
        return int(price * 1_000_000)
    price_str = str(price).strip().lstrip("$").strip()
    try:
        dollars_cents = price_str.split(".")
        dollars = int(dollars_cents[0]) if dollars_cents[0] else 0
        cents = int(dollars_cents[1].ljust(6, "0")[:6]) if len(dollars_cents) > 1 and dollars_cents[1] else 0
        return dollars * 1_000_000 + cents
    except (ValueError, IndexError):
        return 0


def micro_usdc_to_decimal_string(amount: int) -> str:
    whole = amount // 1_000_000
    frac = amount % 1_000_000
    return f"{whole}.{frac:06d}"


def encode_payment_required_payload(payload: dict[str, Any]) -> str:
    return base64.b64encode(json.dumps(payload).encode()).decode()


def enrich_payment_required_payload(payload: dict[str, Any], settings: Any = None) -> dict[str, Any]:
    payload.setdefault("scheme", "exact")
    return payload


def decode_payment_required_header(header_value: str) -> dict[str, Any] | None:
    if not header_value:
        return None
    s = header_value.strip()
    try:
        import base64
        decoded = base64.b64decode(s).decode("utf-8")
        return json.loads(decoded)
    except Exception:
        pass
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        return None


def _file_ext(path: str) -> str:
    idx = path.rfind(".")
    return path[idx:] if idx != -1 else ""


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _is_public_http_url(url: str) -> tuple[bool, str, urllib.parse.ParseResult | None]:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False, "scheme_must_be_http_or_https", parsed
    if not parsed.hostname:
        return False, "missing_hostname", parsed
    if parsed.username or parsed.password:
        return False, "url_must_not_contain_credentials", parsed
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        addresses = socket.getaddrinfo(parsed.hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return False, "hostname_does_not_resolve", parsed
    for item in addresses:
        host = item[4][0]
        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            return False, "resolved_address_is_invalid", parsed
        if not ip.is_global:
            return False, f"resolved_address_not_public:{ip}", parsed
    return True, "public_url", parsed


def _maybe_json_object(text: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _decode_x402_metadata(header_value: str, body_text: str) -> dict[str, Any] | None:
    decoded = decode_payment_required_header(header_value)
    if decoded:
        return decoded
    if header_value.strip().startswith("{"):
        parsed = _maybe_json_object(header_value)
        if parsed:
            return parsed
    parsed_body = _maybe_json_object(body_text)
    if parsed_body:
        return parsed_body
    return None


def _first_accept(metadata: dict[str, Any] | None) -> dict[str, Any]:
    if not metadata:
        return {}
    accepts = metadata.get("accepts", [])
    if isinstance(accepts, list) and accepts:
        return accepts[0] if isinstance(accepts[0], dict) else {}
    return {}


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_domain_health_target(target: str) -> tuple[str, str, urllib.parse.ParseResult | None]:
    if not target:
        return "", "empty_target", None
    target = target.strip()
    if not target.startswith(("http://", "https://")):
        target = "https://" + target
    return _is_public_http_url(target)


def _resolve_public_addresses(hostname: str, port: int) -> tuple[list[str], list[str]]:
    ipv4, ipv6 = [], []
    try:
        addresses = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return ipv4, ipv6
    for item in addresses:
        host = item[4][0]
        if item[0] == socket.AF_INET:
            ipv4.append(host)
        elif item[0] == socket.AF_INET6:
            ipv6.append(host)
    return ipv4, ipv6


def _fetch_domain_http(url: str) -> dict[str, Any]:
    result: dict[str, Any] = {"url": url}
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "x0tta6bl4/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            result["http_status"] = resp.status
            result["content_type"] = resp.headers.get("Content-Type", "")
            result["server"] = resp.headers.get("Server", "")
    except urllib.error.HTTPError as e:
        result["http_status"] = e.code
        result["http_error"] = str(e)
    except (urllib.error.URLError, socket.timeout, OSError) as e:
        result["http_status"] = 0
        result["http_error"] = f"{e.__class__.__name__}: {e}"
    return result


def _check_tls_expiry(hostname: str, port: int = 443) -> dict[str, Any]:
    context = ssl.create_default_context()
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    try:
        with socket.create_connection((hostname, port), timeout=8.0) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as tls:
                cert = tls.getpeercert()
        not_after = cert.get("notAfter") if isinstance(cert, dict) else None
        if not isinstance(not_after, str):
            return {"checked": True, "valid_now": False, "not_after": None, "days_left": None, "error": "missing_not_after"}
        expires_at = datetime.fromtimestamp(ssl.cert_time_to_seconds(not_after), tz=timezone.utc)
        now = datetime.now(timezone.utc)
        days_left = int((expires_at - now).total_seconds() // 86400)
        return {"checked": True, "valid_now": days_left >= 0, "not_after": not_after, "days_left": days_left}
    except Exception as exc:
        return {"checked": False, "valid_now": False, "not_after": None, "days_left": None, "error": exc.__class__.__name__}


class _SnapshotHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.meta_description = ""
        self.headings: list[str] = []
        self.links: list[str] = []
        self._in_title = False
        self._in_heading = False
        self._heading_tag = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_lower = tag.lower()
        if tag_lower == "title":
            self._in_title = True
        elif tag_lower in ("h1", "h2", "h3"):
            self._in_heading = True
            self._heading_tag = tag_lower
        elif tag_lower == "a":
            for name, value in attrs:
                if name and name.lower() == "href" and value:
                    self.links.append(value)

    def handle_endtag(self, tag: str) -> None:
        tag_lower = tag.lower()
        if tag_lower == "title":
            self._in_title = False
        elif tag_lower in ("h1", "h2", "h3"):
            self._in_heading = False

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if not text:
            return
        if self._in_title:
            self.title = (self.title + " " + text).strip()
        if self._in_heading:
            self.headings.append(f"[{self._heading_tag}] {text}")

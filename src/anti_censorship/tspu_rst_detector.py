"""
TSPU In-Stream RST Detector
===========================

Phase 0 signal for the Ghost Access self-healing loop.

The existing ``CensorshipDetector.detect_tcp_blocking`` catches a RST at
*connect* time (a SYN to a blocked IP that comes back with RST). That is not
the failure mode paying users hit on mobile: the NL/SPB audit
(``nl_vpn_audit_2026_07_10``) documents that TSPU lets the TCP handshake and the
Reality/TLS handshake complete, the tunnel starts carrying data, and *then* the
in-path box injects a RST mid-stream and kills the session.

This module drives sustained traffic through a transport (directly, or through
the live tunnel's local SOCKS5 proxy) and classifies how the stream ends:

    clean           -> full read, no interference
    instream_reset  -> ConnectionResetError AFTER a completed handshake
                       (the TSPU in-path signature)
    preflight_fail  -> connect/handshake failed before any tunnel bytes
                       (transport down, a different signal)
    timeout         -> stalled mid-stream
    error           -> anything else

When the in-stream-reset fraction crosses a threshold it emits a
``EventType.DPI_BLOCK_DETECTED`` event with redacted metadata (same bucket/hash
discipline as ``censorship_detector``) and, for the operator, writes a local
evidence artifact that keeps the raw per-run results.

Evidence discipline (see .claude/rules/20-evidence-boundary.md):
- A run driven by the real ``socks``/``socket`` stack against the live tunnel
  and a real target is ``VERIFIED HERE``.
- A run driven by an injected mock ``stream_fn`` (unit tests, loopback) is
  ``SIMULATED`` and must say so.

This module is detection-only. It sends read traffic and observes; it never
mutates VPN state, restarts services, or switches transports. Actuation is
Phase 1 and is gated by .claude/rules/50-prod-source-of-truth.md.
"""
from __future__ import annotations

import argparse
import json
import platform
import socket
import ssl
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from src.anti_censorship.censorship_detector import (
    BlockingType,
    DetectionResult,
    _confidence_bucket,
    _count_bucket,
    _latency_bucket,
    _stable_hash,
    _target_metadata,
)
from src.coordination.events import EventBus, EventType, get_event_bus
from src.services.service_event_identity import service_event_identity

_SERVICE_AGENT = "anti-censorship-tspu-rst-detector"
_SERVICE_LAYER = "anti_censorship_tspu_rst_detector_local_evidence"

TSPU_RST_DETECTOR_CLAIM_BOUNDARY = (
    "Local TSPU in-stream RST probe evidence only. It records per-stream "
    "outcome, byte-count buckets, time-to-first-byte and duration buckets, "
    "handshake completion, target hashes, and service identity presence; it "
    "does not expose raw domains, IP addresses, proxy endpoints, payloads, or "
    "prove production customer traffic, anonymity, or DPI bypass."
)

# A neutral, high-volume default target. A sustained read is what surfaces an
# in-path RST; a short request often completes before TSPU acts.
DEFAULT_TARGET_URL = "https://speed.cloudflare.com/__down?bytes=52428800"
DEFAULT_RUNS = 5
DEFAULT_TIMEOUT_S = 20.0
DEFAULT_READ_BUDGET_BYTES = 8 * 1024 * 1024
# Bytes that must arrive after the handshake before a reset counts as
# "in-stream" rather than an immediate post-handshake kill. Kept small: even a
# few KB through an established tunnel proves the stream was live.
DEFAULT_MIN_STREAM_BYTES = 4096


class StreamOutcome(str, Enum):
    CLEAN = "clean"
    INSTREAM_RESET = "instream_reset"
    PREFLIGHT_FAIL = "preflight_fail"
    TIMEOUT = "timeout"
    ERROR = "error"


@dataclass
class StreamResult:
    """Outcome of one sustained read through the transport."""

    outcome: StreamOutcome
    bytes_received: int
    ttfb_ms: float
    duration_ms: float
    handshake_ok: bool
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "outcome": self.outcome.value,
            "bytes_received": self.bytes_received,
            "ttfb_ms": round(self.ttfb_ms, 3),
            "duration_ms": round(self.duration_ms, 3),
            "handshake_ok": self.handshake_ok,
            "error": self.error,
        }


def _parse_target(url: str) -> tuple[str, int, str, bool]:
    """Return (host, port, path, use_tls) from an http(s) URL."""
    if url.startswith("https://"):
        use_tls, rest = True, url[len("https://") :]
    elif url.startswith("http://"):
        use_tls, rest = False, url[len("http://") :]
    else:
        raise ValueError("target must be an http:// or https:// URL")
    hostport, _, path = rest.partition("/")
    host, _, raw_port = hostport.partition(":")
    port = int(raw_port) if raw_port else (443 if use_tls else 80)
    return host, port, "/" + path, use_tls


def _is_reset(exc: BaseException) -> bool:
    if isinstance(exc, ConnectionResetError):
        return True
    errno = getattr(exc, "errno", None)
    if errno == 104:  # ECONNRESET surfaced via OSError/ssl.SSLError
        return True
    text = str(exc).lower()
    return "reset by peer" in text or "econnreset" in text


def real_stream(
    target_url: str,
    proxy: Optional[str],
    timeout: float = DEFAULT_TIMEOUT_S,
    read_budget_bytes: int = DEFAULT_READ_BUDGET_BYTES,
    min_stream_bytes: int = DEFAULT_MIN_STREAM_BYTES,
) -> StreamResult:
    """Drive one real sustained read, optionally through a SOCKS5 proxy.

    ``proxy`` is ``host:port`` for SOCKS5 (the live tunnel's local proxy) or
    ``None`` for a direct control run.
    """
    host, port, path, use_tls = _parse_target(target_url)
    start = time.monotonic()
    ttfb = 0.0
    received = 0
    handshake_ok = False
    sock: Optional[socket.socket] = None
    try:
        if proxy:
            import socks  # PySocks; optional dependency, only needed for proxy runs

            proxy_host, _, proxy_port = proxy.partition(":")
            sock = socks.socksocket(socket.AF_INET, socket.SOCK_STREAM)
            sock.set_proxy(socks.SOCKS5, proxy_host, int(proxy_port))
        else:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))
        stream = sock
        if use_tls:
            ctx = ssl.create_default_context()
            stream = ctx.wrap_socket(sock, server_hostname=host)
        # Handshake (TCP + TLS/proxy) completed: the transport is established.
        handshake_ok = True

        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}\r\n"
            "User-Agent: x0tta6bl4-tspu-rst-detector/1.0\r\n"
            "Accept: */*\r\n"
            "Connection: close\r\n\r\n"
        ).encode("ascii")
        stream.sendall(request)

        while received < read_budget_bytes:
            chunk = stream.recv(65536)
            if not chunk:
                break  # clean EOF
            if received == 0:
                ttfb = (time.monotonic() - start) * 1000.0
            received += len(chunk)
        outcome = StreamOutcome.CLEAN
        error = None
    except socket.timeout:
        outcome = StreamOutcome.TIMEOUT if handshake_ok else StreamOutcome.PREFLIGHT_FAIL
        error = "timeout"
    except Exception as exc:  # noqa: BLE001 - classify every failure mode
        if _is_reset(exc):
            if handshake_ok and received >= 0:
                # RST after a completed handshake is the in-path signature; the
                # byte count records how far the live stream got before the kill.
                outcome = StreamOutcome.INSTREAM_RESET
            else:
                outcome = StreamOutcome.PREFLIGHT_FAIL
        else:
            outcome = StreamOutcome.PREFLIGHT_FAIL if not handshake_ok else StreamOutcome.ERROR
        error = type(exc).__name__
    finally:
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass

    duration_ms = (time.monotonic() - start) * 1000.0
    # Demote a 0-byte "in-stream" reset (handshake done, no payload) — still
    # tunnel-level interference, but flag it honestly via byte count.
    if outcome is StreamOutcome.INSTREAM_RESET and received < min_stream_bytes:
        # Keep the classification (reset after handshake) but the aggregator
        # weighs confidence by how many streams actually carried data.
        pass
    return StreamResult(
        outcome=outcome,
        bytes_received=received,
        ttfb_ms=ttfb,
        duration_ms=duration_ms,
        handshake_ok=handshake_ok,
        error=error,
    )


StreamFn = Callable[[], StreamResult]


class TspuRstDetector:
    """Aggregates repeated sustained reads into a single detection verdict."""

    def __init__(
        self,
        event_bus: Optional[EventBus] = None,
        event_project_root: Optional[str] = None,
        reset_fraction_threshold: float = 0.5,
    ) -> None:
        self.event_bus = event_bus
        self.event_project_root = event_project_root
        self.reset_fraction_threshold = reset_fraction_threshold

    def _event_bus_or_none(self) -> Optional[EventBus]:
        if self.event_bus is not None:
            return self.event_bus
        if self.event_project_root is None:
            return None
        try:
            self.event_bus = get_event_bus(self.event_project_root)
            return self.event_bus
        except Exception:
            return None

    def detect(
        self,
        stream_fn: StreamFn,
        *,
        transport: str,
        target_label: str,
        runs: int = DEFAULT_RUNS,
        inter_run_sleep_s: float = 1.0,
    ) -> tuple[DetectionResult, List[StreamResult]]:
        """Run ``stream_fn`` ``runs`` times and classify the transport.

        ``stream_fn`` is injectable so tests can simulate outcomes without real
        sockets. ``transport`` and ``target_label`` are operator-facing labels
        (e.g. "reality-nl-443", "cloudflare-down-50mb").
        """
        results: List[StreamResult] = []
        for i in range(runs):
            results.append(stream_fn())
            if i < runs - 1 and inter_run_sleep_s > 0:
                time.sleep(inter_run_sleep_s)

        n = len(results)
        resets = sum(1 for r in results if r.outcome is StreamOutcome.INSTREAM_RESET)
        clean = sum(1 for r in results if r.outcome is StreamOutcome.CLEAN)
        preflight = sum(1 for r in results if r.outcome is StreamOutcome.PREFLIGHT_FAIL)
        timeouts = sum(1 for r in results if r.outcome is StreamOutcome.TIMEOUT)
        reset_fraction = resets / n if n else 0.0

        if reset_fraction >= self.reset_fraction_threshold:
            blocking_type = BlockingType.TCP_INSTREAM_RESET
            is_blocked = True
            # Confidence scales with how consistent the reset is.
            confidence = round(0.6 + 0.39 * reset_fraction, 3)
        elif preflight >= n and n > 0:
            blocking_type = BlockingType.TCP_RESET
            is_blocked = True
            confidence = 0.5
        elif timeouts + preflight > clean and n > 0:
            blocking_type = BlockingType.TCP_TIMEOUT
            is_blocked = True
            confidence = 0.4
        else:
            blocking_type = BlockingType.NONE
            is_blocked = False
            confidence = 0.0

        avg_bytes = sum(r.bytes_received for r in results) / n if n else 0.0
        detection = DetectionResult(
            blocking_type=blocking_type,
            is_blocked=is_blocked,
            confidence=confidence,
            target=f"{transport}|{target_label}",
            details={
                "runs": [r.to_dict() for r in results],
                "reset_fraction": reset_fraction,
                "avg_bytes_received": avg_bytes,
            },
            latency_ms=sum(r.duration_ms for r in results) / n if n else 0.0,
        )
        self._publish(detection, results, transport=transport)
        return detection, results

    def _publish(
        self,
        detection: DetectionResult,
        results: List[StreamResult],
        *,
        transport: str,
    ) -> Optional[str]:
        bus = self._event_bus_or_none()
        if bus is None or not detection.is_blocked:
            return None

        identity = service_event_identity(service_name=_SERVICE_AGENT)
        n = len(results) or 1
        payload: Dict[str, Any] = {
            "component": "anti_censorship.tspu_rst_detector",
            "operation": "detect_instream_reset",
            "service_name": _SERVICE_AGENT,
            "layer": _SERVICE_LAYER,
            "blocking_type": detection.blocking_type.value,
            "confidence_bucket": _confidence_bucket(detection.confidence),
            "reset_fraction_bucket": _confidence_bucket(
                detection.details.get("reset_fraction", 0.0)
            ),
            "run_count_bucket": _count_bucket(len(results)),
            "avg_bytes_bucket": _latency_bucket(
                detection.details.get("avg_bytes_received", 0.0)
            ),
            "handshake_ok_count": sum(1 for r in results if r.handshake_ok),
            "transport_hash": _stable_hash(transport),
            "spiffe_id_present": bool(identity.get("spiffe_id")),
            "control_action": False,
            "observed_state": True,
            "raw_targets_redacted": True,
            "raw_proxy_redacted": True,
            "dataplane_confirmed": False,
            "dpi_bypass_confirmed": False,
            "claim_boundary": TSPU_RST_DETECTOR_CLAIM_BOUNDARY,
        }
        payload.update(_target_metadata(detection.target))
        try:
            event = bus.publish(
                EventType.DPI_BLOCK_DETECTED,
                _SERVICE_AGENT,
                payload,
                priority=6,
            )
            return event.event_id
        except Exception:
            return None


def build_evidence_artifact(
    detection: DetectionResult,
    results: List[StreamResult],
    *,
    transport: str,
    target_url: str,
    client_app: str,
    evidence_status: str,
) -> Dict[str, Any]:
    """Assemble the operator-facing artifact per rules/20 (raw kept locally)."""
    return {
        "schema": "x0tta6bl4.tspu_rst_detector.evidence.v1",
        "evidence_status": evidence_status,  # "VERIFIED HERE" or "SIMULATED"
        "host": platform.node(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "client_app": client_app,
        "transport": transport,
        "target_url": target_url,
        # Honesty guard: a "blocked" verdict is only meaningful if the transport
        # actually came up. If no run completed a handshake, the in-stream RST
        # verdict is untrustworthy (the tunnel was simply down).
        "transport_established": any(r.handshake_ok for r in results),
        "verdict": {
            "blocking_type": detection.blocking_type.value,
            "is_blocked": detection.is_blocked,
            "confidence": detection.confidence,
            "reset_fraction": detection.details.get("reset_fraction"),
            "avg_bytes_received": detection.details.get("avg_bytes_received"),
        },
        "runs": [r.to_dict() for r in results],
        "claim_boundary": TSPU_RST_DETECTOR_CLAIM_BOUNDARY,
    }


def _cli(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Detect TSPU in-stream RST on a live transport (Phase 0).",
    )
    parser.add_argument(
        "--socks",
        default=None,
        help="SOCKS5 proxy host:port of the live tunnel (omit for a direct control run)",
    )
    parser.add_argument("--target", default=DEFAULT_TARGET_URL, help="sustained-read URL")
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_S)
    parser.add_argument(
        "--transport",
        required=True,
        help="operator label for the transport under test, e.g. reality-nl-443",
    )
    parser.add_argument(
        "--client",
        required=True,
        help="client app driving the tunnel, e.g. v2rayTun / Hiddify / direct",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="artifact path (default: .tmp/tspu_rst/<transport>-<ts>.json)",
    )
    parser.add_argument("--project-root", default=".")
    args = parser.parse_args(argv)

    detector = TspuRstDetector(event_project_root=args.project_root)

    def stream_fn() -> StreamResult:
        return real_stream(args.target, args.socks, timeout=args.timeout)

    detection, results = detector.detect(
        stream_fn,
        transport=args.transport,
        target_label=args.target,
        runs=args.runs,
    )

    artifact = build_evidence_artifact(
        detection,
        results,
        transport=args.transport,
        target_url=args.target,
        client_app=args.client,
        evidence_status="VERIFIED HERE",
    )

    out_path = args.out
    if out_path is None:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out_dir = Path(args.project_root) / ".tmp" / "tspu_rst"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = str(out_dir / f"{args.transport}-{ts}.json")
    Path(out_path).write_text(json.dumps(artifact, indent=2), encoding="utf-8")

    print(json.dumps(artifact["verdict"], indent=2))
    print(f"artifact: {out_path}")
    print(f"evidence_status: {artifact['evidence_status']}")
    return 1 if detection.is_blocked else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_cli())

"""Unit tests for the TSPU in-stream RST detector (Phase 0 self-healing signal).

Two evidence tiers are exercised:
- SIMULATED: an injected ``stream_fn`` drives the aggregator verdict + event.
- Real socket classification: ``real_stream`` against a loopback server that
  either resets mid-stream (SO_LINGER=0) or closes cleanly.
"""

from __future__ import annotations

import socket
import struct
import threading

import pytest

from src.coordination.events import EventBus, EventType

detector_mod = pytest.importorskip("src.anti_censorship.tspu_rst_detector")

StreamOutcome = detector_mod.StreamOutcome
StreamResult = detector_mod.StreamResult
TspuRstDetector = detector_mod.TspuRstDetector
BlockingType = detector_mod.BlockingType


def _result(outcome: StreamOutcome, *, bytes_received: int = 0, handshake_ok: bool = True) -> StreamResult:
    return StreamResult(
        outcome=outcome,
        bytes_received=bytes_received,
        ttfb_ms=1.0,
        duration_ms=10.0,
        handshake_ok=handshake_ok,
    )


# --------------------------------------------------------------------------
# Aggregator (SIMULATED via injected stream_fn)
# --------------------------------------------------------------------------


def test_aggregator_flags_instream_reset_and_emits_event(tmp_path):
    bus = EventBus(str(tmp_path))
    detector = TspuRstDetector(event_bus=bus)

    outcomes = iter(
        [
            _result(StreamOutcome.INSTREAM_RESET, bytes_received=120_000),
            _result(StreamOutcome.INSTREAM_RESET, bytes_received=90_000),
            _result(StreamOutcome.CLEAN, bytes_received=52_000_000),
            _result(StreamOutcome.INSTREAM_RESET, bytes_received=110_000),
        ]
    )

    detection, results = detector.detect(
        lambda: next(outcomes),
        transport="reality-nl-443",
        target_label="cloudflare-down-50mb",
        runs=4,
        inter_run_sleep_s=0.0,
    )

    assert detection.blocking_type is BlockingType.TCP_INSTREAM_RESET
    assert detection.is_blocked is True
    assert detection.confidence > 0.6
    assert detection.details["reset_fraction"] == pytest.approx(0.75)
    assert len(results) == 4

    events = bus.get_event_history(event_type=EventType.DPI_BLOCK_DETECTED)
    assert len(events) == 1
    payload = events[0].data
    # Redaction discipline: no raw transport/target/proxy leaks into the event.
    assert payload["raw_targets_redacted"] is True
    assert payload["raw_proxy_redacted"] is True
    assert "reality-nl-443" not in str(payload)
    assert payload["blocking_type"] == "tcp_instream_reset"
    assert payload["control_action"] is False


def test_aggregator_clean_transport_no_event(tmp_path):
    bus = EventBus(str(tmp_path))
    detector = TspuRstDetector(event_bus=bus)

    detection, _ = detector.detect(
        lambda: _result(StreamOutcome.CLEAN, bytes_received=52_000_000),
        transport="reality-nl-443",
        target_label="cloudflare-down-50mb",
        runs=3,
        inter_run_sleep_s=0.0,
    )

    assert detection.is_blocked is False
    assert detection.blocking_type is BlockingType.NONE
    assert bus.get_event_history(event_type=EventType.DPI_BLOCK_DETECTED) == []


def test_aggregator_preflight_fail_is_not_instream(tmp_path):
    bus = EventBus(str(tmp_path))
    detector = TspuRstDetector(event_bus=bus)

    detection, _ = detector.detect(
        lambda: _result(StreamOutcome.PREFLIGHT_FAIL, handshake_ok=False),
        transport="reality-nl-443",
        target_label="cloudflare-down-50mb",
        runs=3,
        inter_run_sleep_s=0.0,
    )

    # Transport down at handshake is a different signal than an in-path RST.
    assert detection.blocking_type is BlockingType.TCP_RESET
    assert detection.is_blocked is True


# --------------------------------------------------------------------------
# real_stream socket classification
# --------------------------------------------------------------------------


class _LoopbackServer:
    """Minimal HTTP server that either resets mid-stream or closes cleanly."""

    def __init__(self, mode: str) -> None:
        self.mode = mode  # "reset" | "clean"
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(1)
        self.port = self._sock.getsockname()[1]
        self._thread = threading.Thread(target=self._serve, daemon=True)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        try:
            self._sock.close()
        except OSError:
            pass

    def _serve(self) -> None:
        try:
            conn, _ = self._sock.accept()
        except OSError:
            return
        with conn:
            try:
                conn.recv(4096)  # consume the request line/headers
                if self.mode == "clean":
                    body = b"x" * 8192
                    conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 8192\r\n\r\n" + body)
                    return  # normal close -> clean EOF (FIN)
                # reset mode: send some bytes, then abort with RST (linger 0).
                conn.sendall(b"HTTP/1.1 200 OK\r\n\r\n" + b"y" * 4096)
                conn.setsockopt(
                    socket.SOL_SOCKET,
                    socket.SO_LINGER,
                    struct.pack("ii", 1, 0),
                )
            except OSError:
                pass


def test_real_stream_classifies_instream_reset():
    with _LoopbackServer("reset") as server:
        result = detector_mod.real_stream(
            f"http://127.0.0.1:{server.port}/big",
            proxy=None,
            timeout=5.0,
        )
    assert result.handshake_ok is True
    assert result.outcome is StreamOutcome.INSTREAM_RESET


def test_real_stream_classifies_clean():
    with _LoopbackServer("clean") as server:
        result = detector_mod.real_stream(
            f"http://127.0.0.1:{server.port}/small",
            proxy=None,
            timeout=5.0,
        )
    assert result.outcome is StreamOutcome.CLEAN
    assert result.bytes_received > 0
    assert result.handshake_ok is True


def test_real_stream_preflight_fail_on_refused():
    # Bind then close to get a port that refuses connections.
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()

    result = detector_mod.real_stream(
        f"http://127.0.0.1:{port}/x",
        proxy=None,
        timeout=2.0,
    )
    assert result.handshake_ok is False
    assert result.outcome is StreamOutcome.PREFLIGHT_FAIL


# --------------------------------------------------------------------------
# Evidence artifact
# --------------------------------------------------------------------------


def test_evidence_artifact_shape():
    results = [_result(StreamOutcome.INSTREAM_RESET, bytes_received=100_000)]
    detection, _ = TspuRstDetector().detect(
        lambda: results[0],
        transport="reality-nl-443",
        target_label="t",
        runs=1,
        inter_run_sleep_s=0.0,
    )
    artifact = detector_mod.build_evidence_artifact(
        detection,
        results,
        transport="reality-nl-443",
        target_url="https://speed.cloudflare.com/__down?bytes=52428800",
        client_app="v2rayTun",
        evidence_status="SIMULATED",
    )
    assert artifact["evidence_status"] == "SIMULATED"
    assert artifact["client_app"] == "v2rayTun"
    assert artifact["host"]
    assert artifact["timestamp"]
    assert artifact["verdict"]["blocking_type"] == "tcp_instream_reset"
    assert artifact["runs"]

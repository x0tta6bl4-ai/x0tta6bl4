"""Unit tests for the Phase 1b sing-box clash-api switch actuator."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, List, Optional

import pytest

mod = pytest.importorskip("src.self_healing.singbox_switch")

ClashApiSelectorBackend = mod.ClashApiSelectorBackend
TransportRung = mod.TransportRung
build_test_singbox_config = mod.build_test_singbox_config


def _rungs() -> List[TransportRung]:
    return [
        TransportRung("reality", "nl-reality", "89.125.1.107", 443, "uuid-x", transport_type="reality", sni="oracle.com", short_id="ab", public_key="pk"),
        TransportRung("xhttp", "nl-xhttp", "89.125.1.107", 443, "uuid-x", transport_type="xhttp", sni="oracle.com", ws_path="/x"),
        TransportRung("ws", "nl-ws", "89.125.1.107", 443, "uuid-x", transport_type="ws", sni="oracle.com", ws_path="/w"),
    ]


# --- config builder -----------------------------------------------------------


def test_build_config_shape():
    cfg = build_test_singbox_config(_rungs(), socks_port=10919, clash_controller="127.0.0.1:10924")
    tags = [o["tag"] for o in cfg["outbounds"]]
    assert "ghost-test-selector" in tags
    assert {"nl-reality", "nl-xhttp", "nl-ws"} <= set(tags)
    selector = next(o for o in cfg["outbounds"] if o["type"] == "selector")
    assert selector["outbounds"] == ["nl-reality", "nl-xhttp", "nl-ws"]
    assert cfg["inbounds"][0]["listen_port"] == 10919
    assert cfg["experimental"]["clash_api"]["external_controller"] == "127.0.0.1:10924"
    assert cfg["route"]["final"] == "ghost-test-selector"


def test_reality_outbound_has_reality_tls():
    ob = _rungs()[0].to_singbox_outbound()
    assert ob["type"] == "vless"
    assert ob["tls"]["reality"]["enabled"] is True
    assert ob["tls"]["reality"]["public_key"] == "pk"
    assert ob["flow"] == "xtls-rprx-vision"


def test_ws_outbound_has_ws_transport():
    ob = _rungs()[2].to_singbox_outbound()
    assert ob["transport"]["type"] == "ws"
    assert ob["transport"]["path"] == "/w"


# --- backend with injected HTTP ----------------------------------------------


class _FakeClash:
    """In-memory clash-api selector."""

    def __init__(self, now: str = "nl-reality") -> None:
        self.now = now
        self.calls: List[tuple[str, str, Optional[Dict[str, Any]]]] = []

    def __call__(self, method: str, url: str, body):
        self.calls.append((method, url, body))
        if method == "PUT":
            self.now = body["name"]
            return 204, None
        if method == "GET":
            return 200, {"now": self.now, "all": ["nl-reality", "nl-xhttp", "nl-ws"]}
        return 404, None


def _backend(fake: _FakeClash, **kw) -> ClashApiSelectorBackend:
    return ClashApiSelectorBackend(
        controller="127.0.0.1:10924",
        selector_tag="ghost-test-selector",
        protocol_to_tag={"reality": "nl-reality", "xhttp": "nl-xhttp", "ws": "nl-ws"},
        test_profile="ghost-test-canary",
        http=fake,
        **kw,
    )


def test_switch_flips_selector_and_verifies():
    fake = _FakeClash(now="nl-reality")
    backend = _backend(fake)
    assert backend.switch_protocol("xhttp", profile="ghost-test-canary") is True
    assert fake.now == "nl-xhttp"
    # PUT then a GET to verify.
    assert [c[0] for c in fake.calls] == ["PUT", "GET"]
    assert backend.switch_log[-1]["ok"] is True


def test_switch_reports_failure_when_selector_did_not_change():
    class _StuckClash(_FakeClash):
        def __call__(self, method, url, body):
            self.calls.append((method, url, body))
            if method == "PUT":
                return 204, None  # accept but do NOT change `now`
            return 200, {"now": self.now}

    fake = _StuckClash(now="nl-reality")
    backend = _backend(fake)
    assert backend.switch_protocol("xhttp") is False
    assert backend.switch_log[-1]["ok"] is False


def test_switch_refuses_non_test_profile():
    backend = _backend(_FakeClash())
    with pytest.raises(PermissionError):
        backend.switch_protocol("xhttp", profile="prod-nl-live")


def test_unknown_protocol_raises():
    backend = _backend(_FakeClash())
    with pytest.raises(ValueError):
        backend.switch_protocol("carrier-pigeon")


# --- real urllib path against a loopback clash-api ---------------------------


class _ClashHandler(BaseHTTPRequestHandler):
    now = "nl-reality"

    def log_message(self, *a):  # silence
        return

    def do_GET(self):
        self._json(200, {"now": type(self).now})

    def do_PUT(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length)) if length else {}
        type(self).now = body.get("name", type(self).now)
        self.send_response(204)
        self.end_headers()

    def _json(self, code, obj):
        payload = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def test_real_urllib_switch_against_loopback_clash_api():
    _ClashHandler.now = "nl-reality"
    server = HTTPServer(("127.0.0.1", 0), _ClashHandler)
    port = server.server_address[1]
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    try:
        backend = ClashApiSelectorBackend(
            controller=f"127.0.0.1:{port}",
            selector_tag="ghost-test-selector",
            protocol_to_tag={"reality": "nl-reality", "xhttp": "nl-xhttp"},
            test_profile="ghost-test-canary",
        )
        assert backend.active() == "nl-reality"
        assert backend.switch_protocol("xhttp") is True
        assert backend.active() == "nl-xhttp"
    finally:
        server.shutdown()

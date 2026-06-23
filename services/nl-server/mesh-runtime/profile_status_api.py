#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOST = "127.0.0.1"
PORT = 9472
STATE_DIR = Path("/opt/x0tta6bl4-mesh/state")
RUNTIME_STATE_PATH = STATE_DIR / "runtime-state.json"
SIGNAL_PATH = STATE_DIR / "listener-loss-signal.json"
HINT_PATH = STATE_DIR / "client-profile-hint.json"


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def build_health() -> dict:
    runtime = load_json(RUNTIME_STATE_PATH)
    signal = load_json(SIGNAL_PATH)
    hint = load_json(HINT_PATH)
    return {
        "generated_at": now_iso(),
        "service": "vps-profile-status-api",
        "runtime_mode": runtime.get("mode"),
        "recommended_action": runtime.get("recommended_action"),
        "listener_signal_status": signal.get("status"),
        "recommended_profile": hint.get("recommended_profile"),
        "ok": bool(runtime),
    }


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            return self._send_json(build_health())
        if self.path == "/runtime-state":
            payload = load_json(RUNTIME_STATE_PATH)
            return self._send_json(payload or {"error": "runtime-state missing"}, 200 if payload else 503)
        if self.path == "/listener-loss-signal":
            payload = load_json(SIGNAL_PATH)
            return self._send_json(payload or {"error": "listener-loss-signal missing"}, 200 if payload else 503)
        if self.path == "/client-profile-hint":
            payload = load_json(HINT_PATH)
            return self._send_json(payload or {"error": "client-profile-hint missing"}, 200 if payload else 503)
        return self._send_json({"error": "not found", "path": self.path}, 404)

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


def main() -> int:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"profile status api listening on http://{HOST}:{PORT}")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

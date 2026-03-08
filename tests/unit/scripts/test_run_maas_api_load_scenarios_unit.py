from __future__ import annotations

import json
import os
import shutil
import socket
import socketserver
import subprocess
import threading
from http.server import BaseHTTPRequestHandler
from pathlib import Path

import pytest


class _LoadScenarioHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path.startswith("/api/v1/maas/marketplace/search"):
            self._write_json(200, [{"listing_id": "lst-1", "currency": "USD"}])
            return
        self._write_json(404, {"detail": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/api/v1/maas/heartbeat":
            self._write_json(200, {"status": "ack"})
            return
        if self.path == "/api/v1/maas/mesh-load-profile/nodes/node-load-profile-001/heartbeat":
            self._write_json(200, {"status": "ok"})
            return
        self._write_json(404, {"detail": "not found"})

    def log_message(self, format: str, *args: object) -> None:
        return

    def _write_json(self, status: int, payload: object) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class _ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True
    block_on_close = False


def _socket_listen_supported() -> bool:
    try:
        probe = socket.socket()
    except PermissionError:
        return False
    except OSError:
        return False

    try:
        probe.bind(("127.0.0.1", 0))
    except OSError:
        return False
    finally:
        probe.close()

    return True


@pytest.fixture
def load_scenario_server() -> str:
    with _ThreadedTCPServer(("127.0.0.1", 0), _LoadScenarioHandler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = server.server_address
            yield f"http://{host}:{port}"
        finally:
            server.shutdown()
            thread.join(timeout=5)


def _script_path() -> Path:
    return Path(__file__).resolve().parents[3] / "scripts" / "ops" / "run_maas_api_load_scenarios.sh"


@pytest.mark.skipif(shutil.which("curl") is None, reason="curl is required by the shell runner")
@pytest.mark.skipif(not _socket_listen_supported(), reason="local socket listen is unavailable in this sandbox")
def test_load_runner_generates_reports_and_latest_artifacts(tmp_path: Path, load_scenario_server: str) -> None:
    report_dir = tmp_path / "reports"
    app_log = tmp_path / "app.log"
    env = os.environ.copy()
    env.update(
        {
            "START_LOCAL_API": "false",
            "BASE_URL": load_scenario_server,
            "REPORT_DIR": str(report_dir),
            "APP_LOG": str(app_log),
            "DURATION_SECONDS": "1",
            "CONCURRENCY": "1",
            "REQUEST_TIMEOUT_SECONDS": "1",
            "SCENARIOS_CSV": "marketplace_search,telemetry_heartbeat,node_heartbeat",
            # Pin NODE_ID to match the mock server handler path; load_dotenv() in src.database
            # may inject NODE_ID=node-001 from .env into the parent process environment, which
            # would otherwise override the script's default (node-load-profile-001).
            "NODE_ID": "node-load-profile-001",
        }
    )

    result = subprocess.run(
        ["bash", str(_script_path())],
        cwd=Path(__file__).resolve().parents[3],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr

    latest_json = report_dir / "MAAS_API_LOAD_SCENARIOS_LATEST.json"
    latest_md = report_dir / "MAAS_API_LOAD_SCENARIOS_LATEST.md"
    assert latest_json.exists()
    assert latest_md.exists()

    data = json.loads(latest_json.read_text(encoding="utf-8"))
    assert data["base_url"] == load_scenario_server
    assert data["requests_total"] > 0
    assert data["requests_error"] == 0
    assert sorted(data["scenarios_selected"]) == [
        "marketplace_search",
        "node_heartbeat",
        "telemetry_heartbeat",
    ]

    report_text = latest_md.read_text(encoding="utf-8")
    assert "Overall:** PASS" in report_text
    assert "marketplace_search" in report_text
    assert "telemetry_heartbeat" in report_text
    assert "node_heartbeat" in report_text


@pytest.mark.skipif(shutil.which("curl") is None, reason="curl is required by the shell runner")
def test_load_runner_returns_config_exit_code_for_unknown_scenario(tmp_path: Path) -> None:
    env = os.environ.copy()
    env.update(
        {
            "START_LOCAL_API": "false",
            "BASE_URL": "http://127.0.0.1:65535",
            "REPORT_DIR": str(tmp_path / "reports"),
            "SCENARIOS_CSV": "unknown_scenario",
        }
    )

    result = subprocess.run(
        ["bash", str(_script_path())],
        cwd=Path(__file__).resolve().parents[3],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 3
    assert "Unknown scenarios in SCENARIOS_CSV" in result.stderr

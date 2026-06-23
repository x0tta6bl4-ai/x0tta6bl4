#!/usr/bin/env python3
"""Keep the x0tta6bl4 x402 paid API reachable.

The script is intentionally small and secret-free. It checks the local paid API,
starts it when it is down, verifies the public agent card and discovery catalog,
then writes a machine-readable status file.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / ".tmp" / "non-bounty"
RUN_DIR = ARTIFACT_DIR / "run"
LOG_DIR = ARTIFACT_DIR / "logs"
DEFAULT_PUBLIC_BASE_URL = "https://saccharolytic-uncatechized-tanika.ngrok-free.dev"
DEFAULT_WALLET = "0x6017613e80d7893EB2aD5c0585b3f1f88CD6e099"
DEFAULT_STATUS_FILE = ARTIFACT_DIR / "x402_paid_api_public_runtime_status.json"
DEFAULT_PID_FILE = RUN_DIR / "x402_paid_api_server.pid"
DEFAULT_LOG_FILE = LOG_DIR / "x402_paid_api.log"
CLAIM_BOUNDARY = (
    "This status proves only local process checks, HTTP reachability, public "
    "discovery metadata, and wallet metadata. It does not prove buyer demand, "
    "paid requests, settlement, or received funds."
)


@dataclass(frozen=True)
class ProbeResult:
    url: str
    ok: bool
    http_status: int | None = None
    payload: dict[str, Any] | None = None
    error: str | None = None
    elapsed_ms: int | None = None


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_pid(path: Path) -> int | None:
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _process_alive(pid: int | None) -> bool:
    if not pid or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _terminate_pid(pid: int | None, timeout_seconds: float = 3.0) -> bool:
    if not _process_alive(pid):
        return False
    assert pid is not None
    os.kill(pid, signal.SIGTERM)
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if not _process_alive(pid):
            return True
        time.sleep(0.1)
    return not _process_alive(pid)


def _json_probe(url: str, timeout_seconds: float) -> ProbeResult:
    start = time.monotonic()
    try:
        request = urllib.request.Request(url, headers={"accept": "application/json"})
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            body = response.read(2_000_000)
            elapsed_ms = int((time.monotonic() - start) * 1000)
            try:
                payload = json.loads(body.decode("utf-8"))
            except json.JSONDecodeError as exc:
                return ProbeResult(
                    url=url,
                    ok=False,
                    http_status=response.status,
                    error=f"invalid_json:{exc}",
                    elapsed_ms=elapsed_ms,
                )
            return ProbeResult(
                url=url,
                ok=200 <= response.status < 300,
                http_status=response.status,
                payload=payload if isinstance(payload, dict) else {"payload": payload},
                elapsed_ms=elapsed_ms,
            )
    except urllib.error.HTTPError as exc:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return ProbeResult(url=url, ok=False, http_status=exc.code, error=f"http_error:{exc.code}", elapsed_ms=elapsed_ms)
    except Exception as exc:  # pragma: no cover - exact socket errors differ by OS.
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return ProbeResult(url=url, ok=False, error=f"{type(exc).__name__}:{exc}", elapsed_ms=elapsed_ms)


def _python_executable() -> str:
    venv_python = ROOT / ".tmp" / "venvs" / "x402-paid-api" / "bin" / "python"
    if venv_python.exists():
        return str(venv_python)
    return sys.executable


def _start_paid_api(host: str, port: int, pid_file: Path, log_file: Path) -> int:
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        env.pop(name, None)
    env["NO_PROXY"] = "*"
    env["no_proxy"] = "*"
    env["PYTHONPATH"] = "."
    cmd = [
        _python_executable(),
        "scripts/ops/run_x402_paid_api.py",
        "--host",
        host,
        "--port",
        str(port),
    ]
    with log_file.open("ab") as log:
        process = subprocess.Popen(
            cmd,
            cwd=ROOT,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    pid_file.write_text(f"{process.pid}\n", encoding="utf-8")
    return process.pid


def _wait_for_local(local_url: str, timeout_seconds: float, deadline_seconds: float = 10.0) -> ProbeResult:
    deadline = time.monotonic() + deadline_seconds
    last = ProbeResult(url=local_url, ok=False, error="not_checked")
    while time.monotonic() < deadline:
        last = _json_probe(local_url, timeout_seconds=timeout_seconds)
        if last.ok:
            return last
        time.sleep(0.4)
    return last


def _extract_wallet(agent_card: ProbeResult) -> str | None:
    if not agent_card.payload:
        return None
    value = agent_card.payload.get("wallet")
    return str(value) if value else None


def _extract_service_count(discovery: ProbeResult) -> int:
    if not discovery.payload:
        return 0
    total = discovery.payload.get("total_services")
    if isinstance(total, int):
        return total
    services = discovery.payload.get("services")
    if isinstance(services, list):
        return len(services)
    return 0


def _extract_first_pay_to(discovery: ProbeResult) -> str | None:
    if not discovery.payload:
        return None
    services = discovery.payload.get("services")
    if not isinstance(services, list) or not services:
        return None
    first = services[0]
    if not isinstance(first, dict):
        return None
    pay_to = first.get("pay_to") or ((first.get("accepts") or {}).get("payTo") if isinstance(first.get("accepts"), dict) else None)
    return str(pay_to) if pay_to else None


def build_status(
    *,
    host: str,
    port: int,
    public_base_url: str,
    expected_wallet: str,
    pid: int | None,
    started_pid: int | None,
    local_health: ProbeResult,
    public_agent_card: ProbeResult,
    public_discovery: ProbeResult,
) -> dict[str, Any]:
    wallet = _extract_wallet(public_agent_card)
    service_count = _extract_service_count(public_discovery)
    first_pay_to = _extract_first_pay_to(public_discovery)
    wallet_matches = wallet == expected_wallet and (first_pay_to in {None, expected_wallet})
    public_ok = public_agent_card.ok and public_discovery.ok and wallet_matches and service_count >= 1
    local_ok = local_health.ok
    if local_ok and public_ok:
        next_action = "keep_watchdog_running"
    elif local_ok:
        next_action = "fix_public_tunnel_or_catalog_visibility"
    else:
        next_action = "restart_local_paid_api"
    return {
        "schema": "x0tta6bl4.x402_paid_api_public_runtime_status.v1",
        "checked_at_utc": utc_now(),
        "claim_boundary": CLAIM_BOUNDARY,
        "expected_wallet": expected_wallet,
        "host": host,
        "port": port,
        "public_base_url": public_base_url.rstrip("/"),
        "pid": pid,
        "started_pid": started_pid,
        "local": {
            "ok": local_ok,
            "health": asdict(local_health),
        },
        "public": {
            "ok": public_ok,
            "agent_card": asdict(public_agent_card),
            "discovery": asdict(public_discovery),
            "wallet": wallet,
            "first_service_pay_to": first_pay_to,
            "wallet_matches": wallet_matches,
            "service_count": service_count,
        },
        "ready_for_paid_calls": bool(local_ok and public_ok),
        "next_action": next_action,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8120)
    parser.add_argument("--public-base-url", default=os.getenv("X0T_PUBLIC_BASE_URL", DEFAULT_PUBLIC_BASE_URL))
    parser.add_argument("--expected-wallet", default=os.getenv("X0T_X402_PAY_TO", DEFAULT_WALLET))
    parser.add_argument("--pid-file", type=Path, default=DEFAULT_PID_FILE)
    parser.add_argument("--log-file", type=Path, default=DEFAULT_LOG_FILE)
    parser.add_argument("--status-file", type=Path, default=DEFAULT_STATUS_FILE)
    parser.add_argument("--timeout-seconds", type=float, default=8.0)
    parser.add_argument("--no-start", action="store_true", help="Only check status; do not start or restart the API.")
    parser.add_argument("--quiet", action="store_true", help="Print one short status line instead of the full JSON report.")
    args = parser.parse_args()

    local_health_url = f"http://{args.host}:{args.port}/health"
    pid = _read_pid(args.pid_file)
    started_pid: int | None = None
    local_health = _json_probe(local_health_url, timeout_seconds=args.timeout_seconds)
    if not local_health.ok and not args.no_start:
        _terminate_pid(pid)
        started_pid = _start_paid_api(args.host, args.port, args.pid_file, args.log_file)
        pid = started_pid
        local_health = _wait_for_local(local_health_url, timeout_seconds=args.timeout_seconds)

    base = args.public_base_url.rstrip("/")
    public_agent_card = _json_probe(f"{base}/.well-known/agent-card.json", timeout_seconds=args.timeout_seconds)
    public_discovery = _json_probe(f"{base}/.well-known/x402-discovery", timeout_seconds=args.timeout_seconds)
    status = build_status(
        host=args.host,
        port=args.port,
        public_base_url=base,
        expected_wallet=args.expected_wallet,
        pid=pid,
        started_pid=started_pid,
        local_health=local_health,
        public_agent_card=public_agent_card,
        public_discovery=public_discovery,
    )
    args.status_file.parent.mkdir(parents=True, exist_ok=True)
    args.status_file.write_text(json.dumps(status, indent=2, sort_keys=True), encoding="utf-8")
    if args.quiet:
        print(
            "ready={ready} local={local} public={public} services={services} next={next_action}".format(
                ready=status["ready_for_paid_calls"],
                local=status["local"]["ok"],
                public=status["public"]["ok"],
                services=status["public"]["service_count"],
                next_action=status["next_action"],
            )
        )
    else:
        print(json.dumps(status, indent=2, sort_keys=True))
    return 0 if status["ready_for_paid_calls"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

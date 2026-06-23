from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ops/ensure_x402_paid_api_public.py"
WALLET = "0x6017613e80d7893EB2aD5c0585b3f1f88CD6e099"


def _load_module():
    spec = importlib.util.spec_from_file_location("ensure_x402_paid_api_public", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_build_status_marks_public_x402_api_ready() -> None:
    mod = _load_module()

    status = mod.build_status(
        host="127.0.0.1",
        port=8120,
        public_base_url="https://public.example",
        expected_wallet=WALLET,
        pid=123,
        started_pid=None,
        local_health=mod.ProbeResult(url="http://127.0.0.1:8120/health", ok=True, http_status=200),
        public_agent_card=mod.ProbeResult(
            url="https://public.example/.well-known/agent-card.json",
            ok=True,
            http_status=200,
            payload={"wallet": WALLET},
        ),
        public_discovery=mod.ProbeResult(
            url="https://public.example/.well-known/x402-discovery",
            ok=True,
            http_status=200,
            payload={"total_services": 8, "services": [{"pay_to": WALLET}]},
        ),
    )

    assert status["ready_for_paid_calls"] is True
    assert status["public"]["wallet_matches"] is True
    assert status["public"]["service_count"] == 8
    assert status["next_action"] == "keep_watchdog_running"


def test_build_status_detects_public_wallet_mismatch() -> None:
    mod = _load_module()

    status = mod.build_status(
        host="127.0.0.1",
        port=8120,
        public_base_url="https://public.example",
        expected_wallet=WALLET,
        pid=123,
        started_pid=None,
        local_health=mod.ProbeResult(url="http://127.0.0.1:8120/health", ok=True, http_status=200),
        public_agent_card=mod.ProbeResult(
            url="https://public.example/.well-known/agent-card.json",
            ok=True,
            http_status=200,
            payload={"wallet": "0x0000000000000000000000000000000000000000"},
        ),
        public_discovery=mod.ProbeResult(
            url="https://public.example/.well-known/x402-discovery",
            ok=True,
            http_status=200,
            payload={"total_services": 8, "services": [{"pay_to": WALLET}]},
        ),
    )

    assert status["ready_for_paid_calls"] is False
    assert status["public"]["wallet_matches"] is False
    assert status["next_action"] == "fix_public_tunnel_or_catalog_visibility"


def test_pid_helpers_handle_missing_or_dead_process(tmp_path: Path) -> None:
    mod = _load_module()
    pid_file = tmp_path / "missing.pid"

    assert mod._read_pid(pid_file) is None
    pid_file.write_text("not-a-pid\n", encoding="utf-8")
    assert mod._read_pid(pid_file) is None
    assert mod._process_alive(-1) is False

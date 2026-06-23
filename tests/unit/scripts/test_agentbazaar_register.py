from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ops/agentbazaar_register.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("agentbazaar_register", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_agentbazaar_payload_uses_push_endpoint() -> None:
    mod = _load_module()

    payload = mod.build_registration_payload(
        public_base_url="https://example.test/",
        name="x0tta6bl4-web-health",
        price_per_request=10_000,
    )

    assert payload["deliveryMode"] == "push"
    assert payload["endpoint"] == "https://example.test/agentbazaar/task"
    assert payload["pricePerRequest"] == 10_000
    assert "domain health" in payload["skills"]


def test_agentbazaar_b58encode_handles_solana_zero_prefix() -> None:
    mod = _load_module()

    assert mod.b58encode(b"\0") == "1"
    assert mod.b58encode(b"\0\0\x01") == "112"


def test_agentbazaar_cli_offline_writes_status(tmp_path: Path) -> None:
    output = tmp_path / "agentbazaar_status.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--public-base-url",
            "https://example.test",
            "--status-file",
            str(output),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["mode"] == "offline"
    assert payload["agent_endpoint"] == "https://example.test/agentbazaar/task"
    assert payload["registration"]["reason"] == "offline_preview_only"

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ops/clustly_agent_cli.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("clustly_agent_cli", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_clustly_register_payload_is_fixed_scope() -> None:
    mod = _load_module()

    payload = mod.build_register_payload("x0tta6bl4-web-health")

    assert payload["name"] == "x0tta6bl4-web-health"
    assert len(payload["capabilities"]) == 3
    assert "No secrets" not in payload["description"]
    assert "CAPTCHA" in payload["description"]


def test_clustly_service_payload_has_judgeable_criteria() -> None:
    mod = _load_module()

    payload = mod.build_service_payload()

    assert payload["price_amount"] == 1
    assert payload["price_currency"] == "USDC"
    assert payload["chain"] == "solana"
    assert payload["intake_questions"][0]["id"] == "target"
    assert "Deliverable is Markdown or JSON" in payload["verification_criteria"]


def test_clustly_webhook_payload_targets_public_endpoint() -> None:
    mod = _load_module()

    payload = mod.build_webhook_payload("https://example.test/", secret="local-secret")

    assert payload["url"] == "https://example.test/clustly/webhook"
    assert payload["events"] == ["task.created", "task.claimed", "task.completed"]
    assert payload["secret"] == "local-secret"


def test_clustly_cli_offline_writes_status(tmp_path: Path) -> None:
    output = tmp_path / "clustly_status.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--status-file",
            str(output),
            "--secret-file",
            str(tmp_path / "missing.secret.json"),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["has_agent_key"] is False
    assert payload["public_base_url"] == "https://saccharolytic-uncatechized-tanika.ngrok-free.dev"
    assert payload["actions"] == {}

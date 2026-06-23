from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ops/run_dataplane_delivery_operator_handoff.py"


def _load_handoff():
    spec = importlib.util.spec_from_file_location(
        "dataplane_delivery_operator_handoff",
        SCRIPT,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_entrypoints(root: Path) -> None:
    for rel in (
        "scripts/ops/collect_dataplane_delivery_eventbus_evidence.py",
        "scripts/ops/run_cross_plane_proof_gate.py",
        "scripts/ops/verify_cross_plane_proof_gate_retention.py",
        "scripts/ops/run_dataplane_delivery_operator_evidence.py",
    ):
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# test entrypoint\n", encoding="utf-8")


def test_handoff_is_ready_for_private_target_without_revealing_raw_host(
    tmp_path: Path,
) -> None:
    handoff = _load_handoff()
    _write_entrypoints(tmp_path)

    report = handoff.build_report(
        tmp_path,
        target_host="10.0.0.5",
        target_port="8443",
        target_label="lab-node-a",
    )

    assert report["ready_for_operator_run"] is True
    assert report["decision"] == handoff.DECISION_READY
    assert report["target"]["raw_target_redacted"] is True
    assert report["target"]["target_is_localish"] is True
    assert report["target"]["host_hash"] == handoff.sha256_text("10.0.0.5")
    assert report["operator_commands"][0]["id"] == (
        "collect_dataplane_delivery_eventbus_evidence"
    )
    command_ids = {command["id"] for command in report["operator_commands"]}
    assert "run_dataplane_delivery_operator_evidence" in command_ids
    assert all(
        check["entrypoint_exists"] is True
        and check["shell_redirection_placeholder_detected"] is False
        for check in report["operator_command_checks"]
    )
    assert "10.0.0.5" not in json.dumps(report)


def test_handoff_blocks_public_or_missing_target(tmp_path: Path) -> None:
    handoff = _load_handoff()
    _write_entrypoints(tmp_path)

    public_report = handoff.build_report(
        tmp_path,
        target_host="8.8.8.8",
        target_port="443",
    )
    missing_report = handoff.build_report(tmp_path)

    assert public_report["ready_for_operator_run"] is False
    assert "target_must_be_loopback_private_or_link_local" in public_report["blockers"]
    assert missing_report["ready_for_operator_run"] is False
    assert "target_host_required" in missing_report["blockers"]
    assert "target_port_required_or_invalid" in missing_report["blockers"]


def test_handoff_cli_require_ready_fails_when_inputs_are_missing() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--root",
            str(ROOT),
            "--require-ready",
            "--json",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["decision"] == "DATAPLANE_DELIVERY_OPERATOR_HANDOFF_BLOCKED_ON_OPERATOR"
    assert "target_host_required" in payload["blockers"]

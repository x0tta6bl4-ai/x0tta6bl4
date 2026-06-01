from __future__ import annotations

import importlib.util
import json
import socket
import subprocess
import sys
import threading
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ops/run_dataplane_delivery_operator_evidence.py"


def load_module():
    spec = importlib.util.spec_from_file_location(
        "run_dataplane_delivery_operator_evidence",
        SCRIPT,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_operator_root(root: Path) -> None:
    for rel in (
        "scripts/ops/collect_dataplane_delivery_eventbus_evidence.py",
        "scripts/ops/run_cross_plane_proof_gate.py",
        "scripts/ops/verify_cross_plane_proof_gate_retention.py",
        "scripts/ops/run_dataplane_delivery_operator_evidence.py",
    ):
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# test entrypoint\n", encoding="utf-8")
    architecture = root / "docs/architecture"
    architecture.mkdir(parents=True, exist_ok=True)
    (architecture / "CURRENT_ACTIVE_GOAL_GAP_AUDIT.md").write_text(
        "# audit\n",
        encoding="utf-8",
    )
    (architecture / "CURRENT_CROSS_PLANE_EVIDENCE_MAP.json").write_text(
        json.dumps(
            {
                "status": "working_map_not_production_completion_proof",
                "planes": {
                    "data_plane": {},
                    "control_plane": {},
                    "trust_plane": {},
                    "evidence_plane": {},
                    "economy_plane": {},
                },
                "cross_plane_links": [
                    {
                        "id": "dataplane-delivery-link",
                        "from_planes": ["data_plane"],
                        "to_planes": ["evidence_plane"],
                        "proof_flags": {
                            "customer_dataplane_delivery_claim_allowed": False,
                            "traffic_delivery_claim_allowed": False,
                        },
                    }
                ],
                "current_gaps": [],
                "next_actions": [],
            }
        ),
        encoding="utf-8",
    )


def _serve_one_loopback_connection() -> tuple[socket.socket, threading.Thread, int]:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = int(server.getsockname()[1])

    def accept_once() -> None:
        try:
            server.settimeout(5.0)
            conn, _addr = server.accept()
            with conn:
                conn.settimeout(1.0)
                try:
                    conn.recv(1)
                except (TimeoutError, socket.timeout):
                    pass
        finally:
            server.close()

    thread = threading.Thread(target=accept_once, daemon=True)
    thread.start()
    return server, thread, port


def test_operator_evidence_runner_dry_run_requires_explicit_probe_flag(
    tmp_path: Path,
) -> None:
    module = load_module()
    _write_operator_root(tmp_path)

    report = module.build_report(
        tmp_path,
        target_host="10.0.0.5",
        target_port="8443",
        target_label="lab-node-a",
    )

    assert report["decision"] == module.DECISION_PROBE_NOT_AUTHORIZED
    assert report["ok"] is False
    assert "allow_operator_probe_required" in report["blockers"]
    assert report["summary"]["probe_attempted"] is False
    assert report["summary"]["event_written"] is False
    assert report["summary"]["writes_eventbus"] is False
    assert "10.0.0.5" not in json.dumps(report)


def test_operator_evidence_runner_blocks_public_target(tmp_path: Path) -> None:
    module = load_module()
    _write_operator_root(tmp_path)

    report = module.build_report(
        tmp_path,
        target_host="8.8.8.8",
        target_port="443",
        target_label="public-target",
        allow_operator_probe=True,
    )

    assert report["decision"] == module.DECISION_INPUT_REQUIRED
    assert report["summary"]["probe_attempted"] is False
    assert "target_must_be_loopback_private_or_link_local" in report["blockers"]
    assert "8.8.8.8" not in json.dumps(report)


def test_operator_evidence_runner_retains_redacted_event_and_reports(
    tmp_path: Path,
) -> None:
    module = load_module()
    _write_operator_root(tmp_path)
    server, thread, port = _serve_one_loopback_connection()
    try:
        output = tmp_path / ".tmp/operator-evidence.json"
        proof_output = tmp_path / ".tmp/proof-gate.json"

        report = module.build_report(
            tmp_path,
            target_host="127.0.0.1",
            target_port=str(port),
            target_label="loopback-smoke",
            allow_operator_probe=True,
            output_json=output,
            proof_gate_output_json=proof_output,
        )
        thread.join(timeout=5.0)
    finally:
        try:
            server.close()
        except OSError:
            pass

    assert report["decision"] == module.DECISION_RETAINED
    assert report["ok"] is True
    assert report["summary"]["probe_attempted"] is True
    assert report["summary"]["event_written"] is True
    assert report["summary"]["proof_gate_report_written"] is True
    assert report["summary"]["operator_run_evidence_retained"] is True
    assert report["summary"]["eventbus_evidence_recognized_by_proof_gate"] is True
    assert report["summary"]["customer_traffic_claimed"] is False
    assert report["summary"]["traffic_delivery_claimed"] is False
    assert report["summary"]["production_readiness_claimed"] is False
    assert report["collector"]["raw_target_redacted"] is True
    assert report["proof_gate"]["artifact_valid"] is True
    assert report["proof_gate"]["selected_event"]["redacted"] is True
    assert report["proof_gate"]["selected_event"]["traffic_delivery_claim_allowed"] is False
    assert output.is_file()
    assert proof_output.is_file()
    assert "127.0.0.1" not in json.dumps(report)


def test_operator_evidence_runner_cli_require_retained_blocks_without_auth(
    tmp_path: Path,
) -> None:
    _write_operator_root(tmp_path)
    output = tmp_path / "operator-evidence.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--root",
            str(tmp_path),
            "--target-host",
            "127.0.0.1",
            "--target-port",
            "18080",
            "--require-retained",
            "--output-json",
            str(output),
            "--json",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["decision"] == "DATAPLANE_OPERATOR_EVIDENCE_PROBE_NOT_AUTHORIZED"
    assert "allow_operator_probe_required" in payload["blockers"]

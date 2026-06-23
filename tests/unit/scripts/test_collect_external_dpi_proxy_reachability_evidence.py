from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parents[3]
COLLECTOR = ROOT / "scripts/ops/collect_external_dpi_proxy_reachability_evidence.py"
VALIDATOR = ROOT / "scripts/ops/verify_external_dpi_proxy_reachability_evidence.py"
IMPORTER = ROOT / "scripts/ops/import_ghost_pulse_external_evidence.py"
CONTRACT = ROOT / "docs/verification/EXTERNAL_DPI_PROXY_REACHABILITY_EVIDENCE_SCHEMA.json"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_contract(root: Path) -> None:
    path = root / "docs/verification/EXTERNAL_DPI_PROXY_REACHABILITY_EVIDENCE_SCHEMA.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(CONTRACT.read_bytes())


def _args(root: Path, *extra: str):
    collector = _load(COLLECTOR, "collect_external_dpi_proxy_reachability_evidence_test_args")
    return collector.parse_args(
        [
            "--root",
            str(root),
            "--target-url",
            "https://blocked.example/probe",
            "--treatment-proxy",
            "socks5h://127.0.0.1:19080",
            "--attempts",
            "2",
            "--timeout-s",
            "1",
            "--operator-or-lab-id",
            "authorized-operator",
            "--authorization-scope-id",
            "ticket-123",
            "--scope-summary",
            "authorized bounded lab run",
            "--network-region-bucket",
            "coarse-region",
            "--network-type",
            "authorized-lab-network",
            "--isp-or-lab-profile",
            "lab-profile-private",
            "--egress-location-bucket",
            "coarse-egress",
            "--policy-context",
            "authorized external DPI lab",
            *extra,
        ]
    )


def test_collector_writes_validator_ready_artifact_for_blocked_control_and_reachable_treatment(tmp_path: Path) -> None:
    collector = _load(COLLECTOR, "collect_external_dpi_proxy_reachability_evidence_test_ready")
    validator = _load(VALIDATOR, "verify_external_dpi_proxy_reachability_evidence_collect_test_ready")
    importer = _load(IMPORTER, "import_ghost_pulse_external_evidence_collect_test_ready")
    _write_contract(tmp_path)

    def fake_runner(command: Sequence[str], timeout: int) -> subprocess.CompletedProcess[str]:
        if "--proxy" in command:
            return subprocess.CompletedProcess(command, 0, stdout="200 0.120 512", stderr="")
        return subprocess.CompletedProcess(command, 0, stdout="451 0.100 64", stderr="")

    report = collector.collect(_args(tmp_path, "--allow-external-probes"), runner=fake_runner)
    candidate = tmp_path / "docs/verification/incoming/dpi_lab.json"
    payload = json.loads(candidate.read_text(encoding="utf-8"))
    validation = validator.build_report(tmp_path)
    import_report = importer.build_report(tmp_path, "dpi_lab", candidate)

    assert report["status"] == "VERIFIED"
    assert payload["schema"] == "x0tta6bl4.ghost_pulse.claim_evidence.v1"
    assert payload["claim_id"] == "dpi_lab"
    assert payload["status"] == "VERIFIED"
    assert payload["artifact_identity"]["claim_id"] == "dpi_lab"
    assert payload["artifact_identity"]["artifact_sha256"] == collector.artifact_content_sha256(payload)
    assert payload["measurements"] == {
        "authorized_lab": True,
        "baseline_detected_or_blocked": True,
        "pulse_result_recorded": True,
        "dpi_bypass_verified": True,
    }
    assert {item["role"] for item in payload["artifacts"]} == {
        "lab_scope",
        "baseline_result",
        "pulse_result",
        "lab_conclusion",
    }
    assert payload["result_summary"]["dpi_bypass_confirmed"] is True
    assert payload["result_summary"]["production_ready"] is False
    assert payload["claim_boundary"]["proof_claims"]["customer_traffic_confirmed"] is False
    assert any(
        item.get("path") == "treatment_proxy_endpoint_hash"
        for item in payload["evidence_links"]["source_hashes"]
        if isinstance(item, dict)
    )
    assert "blocked.example" not in candidate.read_text(encoding="utf-8")
    assert "127.0.0.1" not in candidate.read_text(encoding="utf-8")
    assert validation["decision"] == validator.DECISION_READY
    assert import_report["decision"] == importer.DECISION_READY
    assert import_report["validation"]["status"] == "VERIFIED"
    assert import_report["external_dpi_proxy_validation"]["decision"] == importer.DECISION_READY
    assert report["validator_command_args"] == [
        "python3",
        "scripts/ops/verify_external_dpi_proxy_reachability_evidence.py",
        "--candidate",
        "docs/verification/incoming/dpi_lab.json",
        "--require-ready",
        "--json",
    ]
    assert report["import_preflight_command_args"] == [
        "python3",
        "scripts/ops/import_ghost_pulse_external_evidence.py",
        "--claim",
        "dpi_lab",
        "--candidate",
        "docs/verification/incoming/dpi_lab.json",
        "--require-ready",
        "--json",
    ]
    handoff = report["operator_handoff"]
    assert handoff["schema"] == "x0tta6bl4.external_dpi_proxy.collector_operator_handoff.v1"
    assert handoff["candidate"] == "docs/verification/incoming/dpi_lab.json"
    assert handoff["candidate_sha256"] == collector.sha256_file(candidate)
    assert handoff["redacted_capture_sha256"] == payload["raw_capture_redaction"]["redacted_capture_sha256"]
    assert handoff["commands_redacted"] is True
    assert handoff["raw_inputs_retained"] is False
    assert handoff["read_only_post_collection_commands"][0] == report["validator_command_args"]
    assert handoff["read_only_post_collection_commands"][1] == report["import_preflight_command_args"]
    assert handoff["write_sequence_after_ready"][0] == [
        "python3",
        "scripts/ops/import_ghost_pulse_external_evidence.py",
        "--claim",
        "dpi_lab",
        "--candidate",
        "docs/verification/incoming/dpi_lab.json",
        "--write",
        "--json",
    ]
    assert handoff["write_sequence_after_ready"][-1] == [
        "python3",
        "scripts/ops/run_cross_plane_proof_gate.py",
        "--claim",
        "production_readiness",
        "--claim",
        "dataplane_delivery",
        "--claim",
        "traffic_delivery",
        "--claim",
        "customer_traffic",
        "--claim",
        "settlement_finality",
        "--claim",
        "dpi_bypass",
        "--json",
        "--output-json",
        ".tmp/validation-shards/cross-plane-proof-gate-current.json",
    ]
    handoff_text = json.dumps(handoff, sort_keys=True)
    assert "blocked.example" not in handoff_text
    assert "127.0.0.1" not in handoff_text
    assert "authorized-operator" not in handoff_text
    assert "ticket-123" not in handoff_text
    assert "Do not paste private URLs" in handoff["safe_local_input_rule"]


def test_collector_keeps_artifact_incomplete_when_control_is_reachable(tmp_path: Path) -> None:
    collector = _load(COLLECTOR, "collect_external_dpi_proxy_reachability_evidence_test_incomplete")
    validator = _load(VALIDATOR, "verify_external_dpi_proxy_reachability_evidence_collect_test_incomplete")
    _write_contract(tmp_path)

    def fake_runner(command: Sequence[str], timeout: int) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 0, stdout="200 0.050 128", stderr="")

    report = collector.collect(_args(tmp_path, "--allow-external-probes"), runner=fake_runner)
    validation = validator.build_report(tmp_path)

    assert report["status"] == "INCOMPLETE"
    assert validation["decision"] == validator.DECISION_REJECTED
    assert "result_summary.dpi_bypass_confirmed must be true for DPI lab import readiness" in validation["failures"]


def test_collector_requires_explicit_external_probe_authorization(tmp_path: Path) -> None:
    collector = _load(COLLECTOR, "collect_external_dpi_proxy_reachability_evidence_test_auth")

    def fake_runner(command: Sequence[str], timeout: int) -> subprocess.CompletedProcess[str]:
        raise AssertionError("collector must not run network probes without authorization")

    try:
        collector.collect(_args(tmp_path), runner=fake_runner)
    except SystemExit as exc:
        assert "--allow-external-probes is required" in str(exc)
    else:
        raise AssertionError("collector should require explicit authorization")
